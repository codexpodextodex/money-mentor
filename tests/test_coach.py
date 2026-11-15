"""Profile, peers, mortgage, the explore sandbox, the tools and the number check."""

import duckdb
import pytest

from app import config, db, engine, explore, grounding, insights, mortgage, offline, tools


def test_personas_are_distinct_and_complete():
    people = insights.personas()
    assert len(people) >= 6
    assert len({p["customer_id"] for p in people}) == len(people)
    for p in people:
        profile = insights.spender_profile(p["customer_id"])
        assert profile["spender_type"] in {t["name"] for t in insights.SPENDER_TYPES}
        shares = profile["basket_shares_pct"]
        assert sum(v or 0 for v in shares.values()) == pytest.approx(100, abs=0.3)


def test_every_customer_gets_a_spender_type():
    names = {t["name"] for t in insights.SPENDER_TYPES}
    sample = db.rows("SELECT * FROM cust_features USING SAMPLE 500 ROWS (reservoir, 1)")
    for f in sample:
        assert next(t["name"] for t in insights.SPENDER_TYPES if t["test"](f)) in names


def test_benchmark_matches_raw_and_is_a_percentile():
    cid = "CUST00874"
    path = str(config.DATA_DIR / "tx.parquet").replace("\\", "/")
    monthly = duckdb.connect().execute(
        f"SELECT -sum(amount) / 12.0 FROM read_parquet('{path}') WHERE customer_id = ? AND category = 'Restaurants' "
        "AND tx_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'",
        [cid],
    ).fetchone()[0]
    item = insights.benchmark(cid, "restaurants")["comparisons"][0]
    assert item["you"] == pytest.approx(monthly, abs=0.01)
    assert 0 <= item["higher_than_pct_of_peers"] <= 100
    assert item["peers"] > 50
    overview = insights.benchmark(cid)["comparisons"]
    assert len(overview) == 5
    with pytest.raises(engine.EngineError):
        insights.benchmark(cid, "restaurants", peer_group="friends")


def test_mortgage_patterns_come_from_the_data():
    pat = mortgage.patterns()
    assert pat["applications"] == 200 and pat["approved"]["count"] == 150 and pat["rejected"] == 50
    factor = db.scalar("SELECT median(required_monthly_income / requested_loan) FROM mtg_final")
    assert pat["income_factor"] == pytest.approx(factor)
    assert sum(r["count"] for r in pat["rejections"]) == 50


def test_mortgage_readiness_arithmetic():
    r = mortgage.readiness("CUST00874", property_price=250000, own_money=40000)
    assert r["home"]["loan"] == 210000
    assert r["home"]["own_money_share_pct"] == pytest.approx(16.0)
    assert len(r["pillars"]) == 4
    assert all(p["status"] in {"strong", "close", "not_yet"} for p in r["pillars"])
    assert "not a credit decision" in r["note"]
    pat = mortgage.patterns()
    assert r["you"]["largest_loan_your_income_supports"] == pytest.approx(
        r["you"]["monthly_income"] / pat["income_factor"], rel=0.001
    )


def test_mortgage_applicant_sees_their_own_application():
    rejected = db.scalar("SELECT customer_id FROM mtg_final WHERE final_decision = 'rejected' ORDER BY 1 LIMIT 1")
    r = mortgage.readiness(rejected)
    assert r["your_application"]["decision"] == "rejected"
    assert r["home"]["property_price"] == r["your_application"]["property_price"]
    timeline = mortgage.application_timeline(rejected)
    assert timeline["has_application"]
    assert [e["event"] for e in timeline["timeline"]].count("loan_decision") == 1
    assert timeline["started"] <= timeline["decided"] and timeline["days"] >= 0
    assert mortgage.application_timeline("CUST00001")["has_application"] in (True, False)


def test_explore_sees_only_the_customers_own_rows():
    cid = "CUST00874"
    own = db.scalar("SELECT count(*) FROM tx WHERE customer_id = ?", [cid])
    got = explore.run(cid, "SELECT count(*) AS n, round(sum(spent), 2) AS spent FROM my_transactions")
    assert got["rows"][0][0] == own
    spent = db.scalar("SELECT -sum(amount) FROM tx WHERE customer_id = ? AND amount < 0", [cid])
    assert got["rows"][0][1] == pytest.approx(spent, abs=0.01)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM tx",
        "SELECT * FROM customers",
        "SELECT * FROM read_parquet('data/tx.parquet')",
        "SELECT * FROM read_csv('C:/Windows/win.ini')",
        "DROP TABLE my_transactions",
        "DELETE FROM my_transactions",
        "SELECT 1; SELECT 2",
        "COPY my_transactions TO 'leak.csv'",
        "ATTACH 'other.db'",
        "",
    ],
)
def test_explore_refuses_everything_else(sql):
    with pytest.raises(engine.EngineError):
        explore.run("CUST00874", sql)


def test_explore_limits_rows():
    got = explore.run("CUST00874", "SELECT * FROM my_transactions")
    assert got["row_count"] == explore.MAX_ROWS and got["truncated"]


def test_tools_never_accept_a_customer_id():
    for spec in tools.TOOL_SPECS:
        assert "customer_id" not in spec["function"]["parameters"]["properties"]
    assert {s["function"]["name"] for s in tools.TOOL_SPECS} == set(tools.TOOL_NAMES)
    assert "error" in tools.call("CUST00874", "get_spending", {"customer_id": "CUST00001"})
    assert "error" in tools.call("CUST00874", "no_such_tool", {})
    assert "error" in tools.call("CUST00874", "get_spending", {"category": "nonsense"})
    assert tools.call("CUST00874", "get_spending", {"period": "last_month", "subcategory": ""})["filters"] == {}


@pytest.mark.parametrize("name", tools.TOOL_NAMES)
def test_every_tool_runs(name):
    args = {
        "simulate_change": {"target": "Restaurants", "change_pct": -20},
        "check_affordability": {"amount": 50},
        "prepare_payment": {"amount": 84.6, "iban": "FI87 9999 9900 0123 44"},
        "run_sql": {"sql": "SELECT count(*) FROM my_transactions"},
    }.get(name, {})
    assert "error" not in tools.call("CUST00874", name, args)


@pytest.mark.parametrize(
    "question, tool, expected",
    [
        ("How much did I spend on taxis last month?", "get_spending", {"period": "last_month", "subcategory": "taxis"}),
        ("What kind of spender am I?", "get_spender_profile", {}),
        ("What is safe for me to spend this week?", "get_safe_to_spend", {}),
        (
            "How much could I save if I reduced dining out by 20%?",
            "simulate_change",
            {"target": "dining out", "change_pct": -20.0},
        ),
        ("Where did my money go?", "get_baskets", {}),
        ("Could I get a mortgage for a 250000 home?", "get_mortgage_readiness", {"property_price": 250000.0}),
    ],
)
def test_keyword_router_handles_the_brief_questions(question, tool, expected):
    assert offline.route(question) == (tool, expected)


@pytest.mark.parametrize("cid", ["CUST00086", "CUST00874", "CUST02396", "CUST00728"])
def test_can_afford_follows_safe_to_spend(cid):
    safe = engine.safe_to_spend(cid)
    cover = safe["balance_check"]["balance_can_cover"]
    week = safe["this_week"]["safe_to_spend"]
    until = safe["safe_to_spend_until_payday"]

    small = engine.can_afford(cid, 1, "a coffee")
    assert small["item"]["basket"] == "Everyday spending"
    assert small["fits"] == ("no" if cover < 1 else "yes" if week >= 1 else "tight" if until >= 1 else "not_from_this_budget")

    huge = engine.can_afford(cid, max(cover, 0) + 5000, "a holiday", "Travel")
    assert huge["fits"] == "no" and huge["balance_left_after"] < 0

    if cover > until + 50:
        over = engine.can_afford(cid, until + 25, "a jacket", "Lifestyle")
        assert over["fits"] == "not_from_this_budget"
        assert over["everyday_budget"]["left_until_payday_after"] == pytest.approx(-25, abs=0.02)


def test_can_afford_puts_necessities_in_the_right_basket():
    assert engine.can_afford("CUST02396", 40, "pharmacy", "Health")["item"]["basket"] == "Unexpected necessities"
    assert engine.can_afford("CUST02396", 450, "washing machine", "Home & Tech")["item"]["basket"] == "Unexpected necessities"
    assert engine.can_afford("CUST02396", 45, "a lamp", "home and tech")["item"]["basket"] == "Everyday spending"
    assert engine.can_afford("CUST02396", 60, "food", "Groceries")["item"]["basket"] == "Regular essentials"
    for bad in (0, -5, "abc"):
        with pytest.raises(engine.EngineError):
            engine.can_afford("CUST02396", bad)
    with pytest.raises(engine.EngineError):
        engine.can_afford("CUST02396", 10, category="nonsense")


@pytest.mark.parametrize("cid", ["CUST00086", "CUST00874", "CUST02396", "CUST00728"])
def test_a_large_purchase_gets_both_readings(cid):
    """The price alone cannot tell a replaced appliance from a treat, so both verdicts are given."""
    safe = engine.safe_to_spend(cid)
    cover = safe["balance_check"]["balance_can_cover"]
    until = safe["safe_to_spend_until_payday"]
    usual = safe["usual_everyday_per_day"] * safe["pay_period"]["days_left"]

    got = engine.can_afford(cid, 349, "headphones", "Home & Tech")
    assert got["item"]["basket"] == "Unexpected necessities"
    assert "basket_depends_on" in got["item"]
    if cover < 349:
        assert got["fits"] == "no" and "if_it_is_a_treat" not in got
        return
    # as a necessity: fine only if it leaves the usual everyday money until payday
    assert got["fits"] == ("tight" if cover - 349 < usual else "yes")
    assert got["until_payday"]["left_for_everyday_spending_after"] == pytest.approx(cover - 349, abs=0.02)
    # as a treat: the same verdict an everyday purchase of that size gets
    treat = got["if_it_is_a_treat"]
    assert treat["basket"] == "Everyday spending"
    same_as_everyday = engine.can_afford(cid, 349, "headphones", "Lifestyle")
    assert treat["fits"] == same_as_everyday["fits"]
    assert treat["everyday_budget"] == same_as_everyday["everyday_budget"]
    if until < 349:
        assert treat["fits"] == "not_from_this_budget"


def test_only_the_size_rule_gets_a_second_reading():
    assert "if_it_is_a_treat" not in engine.can_afford("CUST02396", 40, "pharmacy", "Health")
    assert "if_it_is_a_treat" not in engine.can_afford("CUST02396", 45, "a lamp", "Home & Tech")
    assert "if_it_is_a_treat" not in engine.can_afford("CUST02396", 60, "food", "Groceries")
    assert "if_it_is_a_treat" in engine.can_afford("CUST02396", 450, "car repair", "Transportation")


def test_an_over_budget_customer_is_not_told_a_plain_yes():
    """CUST00086 has already used this pay period's everyday budget."""
    safe = engine.safe_to_spend("CUST00086")
    assert safe["status"] == "over_budget"
    cover = safe["balance_check"]["balance_can_cover"]
    # With the rent still to come before payday, 349 euros is more than the balance can carry.
    got = engine.can_afford("CUST00086", 349, "headphones", "Home & Tech")
    assert cover < 349 and got["fits"] == "no" and "if_it_is_a_treat" not in got
    assert offline.describe("check_affordability", got).startswith("Not right now.")
    # Something the balance does carry is still not a plain yes for someone over budget.
    small = engine.can_afford("CUST00086", 40, "a shirt", "Lifestyle")
    assert cover >= 40 and small["fits"] == "not_from_this_budget"


def test_a_filtered_total_carries_the_payments_it_counted():
    got = engine.spending("CUST00086", period="last_3_months", subcategory="fast food")
    assert got["filters"] == {"subcategory": "Fast food"}
    counted = got["counted"]
    assert counted["of"] == got["transactions"] and counted["shown"] == len(counted["payments"]) <= engine.COUNTED_SHOWN
    assert {p["subcategory"] for p in counted["payments"]} == {"Fast food"}
    if counted["shown"] == counted["of"]:
        assert sum(p["amount"] for p in counted["payments"]) == pytest.approx(got["total"], abs=0.02)
    dates = [p["date"] for p in counted["payments"]]
    assert dates == sorted(dates, reverse=True)
    # an unfiltered total has thousands of payments behind it, so it carries none
    assert "counted" not in engine.spending("CUST00086", period="last_3_months")
    # the model answers from the total: the single payments stay with the app
    assert "counted" not in grounding.for_model(got) and grounding.for_model(got)["total"] == got["total"]


def test_everyday_words_cover_every_matching_kind_of_shop():
    clothes = engine.spending("CUST00086", period="last_3_months", subcategory="clothes")
    assert clothes["filters"] == {"subcategory": "Family clothing and Clothing stores"}
    both = sum(
        engine.spending("CUST00086", period="last_3_months", subcategory=name)["total"]
        for name in ("Family clothing", "Clothing stores")
    )
    assert clothes["total"] == pytest.approx(both, abs=0.02)
    for word, expected in [("pikaruoka", "Fast food"), ("snabbmat", "Fast food"), ("burgers", "Fast food"), ("taksi", "Taxis")]:
        assert engine.resolve_target(word)["values"] == [expected]
    assert engine.resolve_target("vaatteet")["values"] == ["Family clothing", "Clothing stores"]
    assert engine.resolve_target("kläder")["values"] == ["Family clothing", "Clothing stores"]


def test_basket_for_a_new_purchase_matches_the_sql_rules():
    """The Python rule used for 'can I afford this' must agree with the SQL rule used for history."""
    rows = db.rows(
        "SELECT category, -amount AS amount, basket FROM tx WHERE tx_type = 'purchase' AND mcc IS DISTINCT FROM '4121' "
        "USING SAMPLE 3000 ROWS (reservoir, 3)"
    )
    for r in rows:
        assert engine.basket_for_purchase(r["category"], r["amount"])[0] == r["basket"], r


def test_keyword_router_extra_routes():
    assert offline.route("Can I afford 89 euros for shoes?") == ("check_affordability", {"amount": 89.0})
    assert offline.route("Anything I should know?") == ("get_highlights", {})
    assert offline.route("How could I save more?") == ("replay_year", {})
    events = list(offline.run("CUST00874", "Can I afford this?", has_image=True))
    assert events[-1]["type"] == "answer" and "photo" in events[-1]["text"].lower() and len(events) == 1


def test_keyword_router_answers_are_grounded():
    for question in ("How much did I spend on taxis last month?", "What is safe for me to spend this week?"):
        events = list(offline.run("CUST00874", question))
        results = [e["result"] for e in events if e["type"] == "tool_result"]
        answer = events[-1]
        assert answer["type"] == "answer" and answer["mode"] == "offline"
        assert grounding.check(answer["text"], results, question)["ok"]


def test_number_check_catches_an_invented_number():
    result = {"total": 1234.56, "previous_period": {"change_pct": 20.0}, "period": {"end": "2026-10-15"}}
    ok = grounding.check("You spent €1,234.56, about 1 235 euros, 20% more. Payday is on the 15th.", [result])
    assert ok["ok"] and ok["numbers_checked"] == 4
    bad = grounding.check("You spent €1,234.56 and could save €999 a year.", [result])
    assert not bad["ok"] and bad["unverified"] == ["999"]
    assert grounding.check("Cutting 20% saves 50 euros.", [{"saving": 50}], question="cut by 20%")["ok"]


def test_number_check_reads_finnish_dates_as_dates():
    result = {"pay_period": {"next_payday": "2026-10-15"}, "safe_to_spend_until_payday": 52.9}
    # 15.10. is the 15th of October, not the number 15.1
    assert grounding.check("Seuraava palkkapäivä on 15.10. ja turvallista käyttää on 52,90 €.", [result])["ok"]
    assert grounding.check("Palkkapäivä on 15.10.2026.", [result])["ok"]
    # a date that is not in the data is still caught, by its day
    assert grounding.check("Palkkapäivä on 23.10.", [result])["unverified"] == ["23"]
    # an amount at the end of a sentence stays an amount
    assert grounding.check("Voit käyttää 17.12 €.", [result])["unverified"] == ["17.12"]
    assert grounding.check("You could save €17.12.", [result])["unverified"] == ["17.12"]


def test_number_parsing_in_finnish_and_english():
    assert grounding.parse_number("1 234,50") == 1234.5
    assert grounding.parse_number("1,234.50") == 1234.5
    assert grounding.parse_number("3,000") == 3000
    assert grounding.parse_number("12,5") == 12.5
