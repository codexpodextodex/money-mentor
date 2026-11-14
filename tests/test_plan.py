"""Looking ahead: the payday plan adds up, and the outlook is plain arithmetic on the usual pattern."""

import datetime as dt

import pytest

from app import db, engine, grounding, insights, offline, plan, tools

CUSTOMERS = ["CUST00086", "CUST00874", "CUST00728", "CUST02396", "CUST00001"]


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_payday_plan_splits_the_whole_salary(cid):
    got = plan.payday_plan(cid)
    salary = got["payday"]["expected_salary"]
    keys = [row["key"] for row in got["split"]]
    assert keys[0] == "essentials" and keys[-1] == "everyday" and keys[-2] == "savings" and "unexpected" in keys
    assert all(row["amount"] >= 0 for row in got["split"])
    if got["fits"]:
        assert got["adds_up_to"] == pytest.approx(salary, abs=0.05)
    else:
        assert got["short_by"] > 0 and got["adds_up_to"] > salary
    everyday = got["split"][-1]
    days = got["pay_period"]["days"]
    assert 28 <= days <= 31
    assert everyday["a_week"] == pytest.approx(everyday["amount"] / days * 7, abs=0.02)
    essentials = got["split"][0]
    assert sum(p["amount"] for p in essentials["parts"]) == pytest.approx(essentials["amount"], abs=0.05)
    assert got["payday"]["date"] == got["pay_period"]["from"] and got["payday"]["in_days"] >= 1


def test_payday_plan_savings_follow_the_goal_and_give_way_first():
    low = plan.payday_plan("CUST00874", 5)
    high = plan.payday_plan("CUST00874", 20)
    saving = {p["savings_goal_pct"]: next(r for r in p["split"] if r["key"] == "savings") for p in (low, high)}
    everyday = {p["savings_goal_pct"]: p["split"][-1]["amount"] for p in (low, high)}
    assert saving[20]["amount"] > saving[5]["amount"]
    # what goes to savings comes out of everyday spending, euro for euro
    assert saving[20]["amount"] - saving[5]["amount"] == pytest.approx(everyday[5] - everyday[20], abs=0.05)
    # a goal the salary cannot carry is cut back, and the plan still adds up to the salary
    stretched = plan.payday_plan("CUST00086", 60)
    kept = next(r for r in stretched["split"] if r["key"] == "savings")
    assert kept["goal_kept"] is False and stretched["split"][-1]["amount"] == 0
    assert stretched["fits"] and stretched["tight"] and "why_it_is_tight" in stretched
    assert stretched["adds_up_to"] == pytest.approx(stretched["payday"]["expected_salary"], abs=0.05)
    # the rent is planned in full, the way the outlook expects it
    rent = next(p["amount"] for p in stretched["split"][0]["parts"] if p["label"] == "Housing payment")
    assert rent == plan.outlook("CUST00086")["assumes"]["bills"][0]["amount"]


def test_payday_plan_shows_the_last_full_pay_period():
    got = plan.payday_plan("CUST00086")
    last = got["last_pay_period"]
    spent = db.scalar(
        "SELECT -sum(amount) FROM tx WHERE customer_id = 'CUST00086' AND flow = 'spend' AND basket = 'everyday' AND tx_date BETWEEN ? AND ?",
        [last["from"], last["to"]],
    )
    assert last["everyday"] == pytest.approx(spent, abs=0.02)
    # the period is the usual month from payday to payday, whenever the salary actually arrived
    assert (last["from"], last["to"], last["days"]) == ("2026-08-15", "2026-09-14", 31)
    # the difference is said in words: exactly one of the two, never a signed number
    more, less = "everyday_then_was_more_than_this_plan_by", "this_plan_has_more_for_everyday_by"
    assert (more in last) != (less in last)
    assert last[more] == pytest.approx(last["everyday"] - got["split"][-1]["amount"], abs=0.02)
    roomy = plan.payday_plan("CUST00874")
    assert 28 <= roomy["last_pay_period"]["days"] <= 31
    assert roomy["last_pay_period"][less] == pytest.approx(roomy["split"][-1]["amount"] - roomy["last_pay_period"]["everyday"], abs=0.02)


def test_savings_name_the_saving_service_only_for_what_is_not_automatic():
    for cid in CUSTOMERS:
        row = next(r for r in plan.payday_plan(cid)["split"] if r["key"] == "savings")
        beyond = row["amount"] - row["already_automatic"]
        assert (row["to"] == "Säästäjä") == (beyond >= 0.005)


def test_when_everyday_spending_alone_cannot_fix_it_the_gap_is_never_negative():
    # CUST00034: the salary does not cover the essentials.
    got = plan.outlook("CUST00034")
    h = got["heads_up"]
    assert h["fix"] is None and h["everyday_spending_alone_is_not_enough"]["still_short_by"] >= 0
    assert h["days_below_zero"] <= h["out_of_the_days_shown"] == got["days"]


def test_expected_bills_count_a_monthly_bill_once_per_month():
    # CUST00086 paid housing on 6 August 2026.
    before = engine.expected_bills("CUST00086", dt.date(2026, 8, 5), dt.date(2026, 8, 6), dt.date(2026, 9, 14))
    after = engine.expected_bills("CUST00086", dt.date(2026, 8, 10), dt.date(2026, 8, 11), dt.date(2026, 9, 14))
    months = lambda bills: [(b["date"].month, b["tx_type"]) for b in bills["dated"]]  # noqa: E731
    assert (8, "housing_payment") in months(before)  # not paid yet: expected in August
    assert (8, "housing_payment") not in months(after)  # paid: not expected again
    assert (9, "housing_payment") in months(after)
    # bills that come several times a month are a daily rate, not dates
    assert "utilities_payment" in after["per_day"] and all(b["tx_type"] != "utilities_payment" for b in after["dated"])
    assert all(dt.date(2026, 8, 11) <= b["date"] <= dt.date(2026, 9, 14) for b in after["dated"])


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_safe_to_spend_counts_the_same_bills(cid):
    safe = engine.safe_to_spend(cid)
    check = safe["balance_check"]
    dated = sum(b["amount"] for b in check["bills_expected"])
    assert check["bills_due_before_payday"] >= dated - 0.05
    assert check["balance_can_cover"] == pytest.approx(
        check["balance_today"] + check["salary_expected_tomorrow"] - check["bills_due_before_payday"] - check["groceries_and_transport_before_payday"],
        abs=0.05,
    )


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_outlook_is_plain_arithmetic(cid):
    got = plan.outlook(cid)
    series = got["series"]
    assert len(series["dates"]) == len(series["balance"]) == got["days"]
    assert series["dates"][0] == (db.today() + dt.timedelta(days=1)).isoformat() and series["dates"][-1] == got["until"]
    a = got["assumes"]
    paydays = [d for d in series["dates"] if dt.date.fromisoformat(d).day == dt.date.fromisoformat(got["next_payday"]).day]
    bills = sum(b["amount"] for b in a["bills"])
    per_day = a["other_bills_a_day"] + a["groceries_and_transport_a_day"] + a["everyday_spending_a_day"]
    expected_end = got["balance_today"] + a["salary"] * len(paydays) - bills - per_day * got["days"]
    assert series["balance"][-1] == pytest.approx(expected_end, abs=1.0)
    assert got["lowest_point"]["balance"] == pytest.approx(min(series["balance"]), abs=0.01)
    below = [b for b in series["balance"] if b < 0]
    assert (got["status"] == "short") == bool(below) == ("heads_up" in got)
    assert "series" not in grounding.for_model(got)


def test_the_heads_up_names_the_bill_and_a_fix_that_works():
    got = plan.outlook("CUST00086")
    h = got["heads_up"]
    assert h["below_zero_from"] <= h["deepest_point"]["date"] <= got["until"]
    assert h["short_by"] == pytest.approx(-got["lowest_point"]["balance"], abs=0.01)
    assert h["biggest_bill_before"]["what"] == "Housing payment" and h["biggest_bill_before"]["date"] <= h["below_zero_from"]
    fix = h["fix"]
    assert 0 <= fix["everyday_spending_a_day"] < fix["instead_of_your_usual"]
    assert fix["a_week"] == pytest.approx(fix["everyday_spending_a_day"] * 7, abs=0.02)
    # with the lower pace the balance never goes below zero
    assert min(got["series"]["with_the_fix"]) >= 0 and fix["lowest_point_then"] >= 0
    assert fix["lowest_point_then"] < 5  # and it is the gentlest level that does so


def test_the_heads_up_leads_the_notices_and_carries_its_facts():
    notices = insights.notices("CUST00086")["notices"]
    first = notices[0]
    assert first["kind"] == "heads_up" and first["tone"] == "warning"
    assert first["data"]["short_by"] == plan.outlook("CUST00086")["heads_up"]["short_by"]
    # a customer with plenty of money gets no such notice
    assert all(n["kind"] != "heads_up" for n in insights.notices("CUST02396")["notices"])


def test_the_coach_can_reach_both():
    assert {"get_payday_plan", "get_balance_outlook"} <= set(tools.TOOL_NAMES)
    assert tools.call("CUST00086", "get_payday_plan", {"savings_goal_pct": 5})["savings_goal_pct"] == 5
    assert offline.route("How should I split my salary?") == ("get_payday_plan", {})
    assert offline.route("Will my money last until payday?") == ("get_balance_outlook", {})
    # the question the heads-up notice hands to the chat
    ask = next(n["ask"] for n in insights.notices("CUST00086")["notices"] if n["kind"] == "heads_up")
    assert offline.route(ask) == ("get_balance_outlook", {})
    said = offline.describe("get_balance_outlook", plan.outlook("CUST00086"))
    assert "below zero" in said and "not a forecast" in said
    calm = offline.describe("get_balance_outlook", plan.outlook("CUST02396"))
    assert "stays above zero" in calm
    assert "a week" in offline.describe("get_payday_plan", plan.payday_plan("CUST00086"))
