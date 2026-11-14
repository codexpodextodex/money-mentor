"""The engine's numbers, checked against independent SQL over the raw Parquet file.

The `raw` fixture reads data/tx.parquet directly and knows nothing about the
engine's derived tables, baskets or period logic.
"""

import datetime as dt

import duckdb
import pytest

from app import config, db, engine, periods

CUSTOMERS = ["CUST00001", "CUST00003", "CUST00086", "CUST00874", "CUST02396", "CUST04457"]
NOT_SPENDING = "('salary', 'other_income', 'investment_deposit', 'investment_withdrawal', 'salary_sweep')"


@pytest.fixture(scope="module")
def raw():
    path = str(config.DATA_DIR / "tx.parquet").replace("\\", "/")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet('{path}')")
    return con


def test_today_is_the_last_day_in_the_data(raw):
    assert db.today() == raw.execute("SELECT max(tx_date) FROM raw").fetchone()[0] == dt.date(2026, 9, 30)


def test_every_row_is_loaded(raw):
    assert db.scalar("SELECT count(*) FROM tx") == raw.execute("SELECT count(*) FROM raw").fetchone()[0]


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_taxis_last_month(raw, cid):
    """'How much did I spend on taxis last month?' Taxis are MCC 4121; last month is August 2026."""
    total, n = raw.execute(
        "SELECT coalesce(-sum(amount), 0), count(*) FROM raw WHERE customer_id = ? AND mcc = '4121' "
        "AND tx_date BETWEEN DATE '2026-08-01' AND DATE '2026-08-31'",
        [cid],
    ).fetchone()
    got = engine.spending(cid, "last_month", subcategory="taxis")
    assert got["period"]["start"] == "2026-08-01" and got["period"]["end"] == "2026-08-31"
    assert got["total"] == pytest.approx(total, abs=0.01)
    assert got["transactions"] == n


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_dining_out_cut_by_20_percent(raw, cid):
    """'How much could I save if I reduced dining out by 20%?' Baseline: last 6 complete months."""
    monthly = raw.execute(
        "SELECT coalesce(-sum(amount), 0) / 6.0 FROM raw WHERE customer_id = ? AND category = 'Restaurants' "
        "AND tx_date BETWEEN DATE '2026-04-01' AND DATE '2026-09-30'",
        [cid],
    ).fetchone()[0]
    got = engine.what_if(cid, "dining out", -20)
    assert got["target"] == "Restaurants"
    assert got["monthly_now"] == pytest.approx(monthly, abs=0.01)
    assert got["monthly_saving"] == pytest.approx(0.2 * monthly, abs=0.01)
    assert got["yearly_saving"] == pytest.approx(12 * 0.2 * monthly, abs=0.02)


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_baskets_add_up_to_all_spending(raw, cid):
    spend = raw.execute(
        f"SELECT coalesce(-sum(amount), 0) FROM raw WHERE customer_id = ? AND amount < 0 AND transaction_type_is_spend "
        "AND tx_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'".replace(
            "transaction_type_is_spend", f"tx_type NOT IN {NOT_SPENDING}"
        ),
        [cid],
    ).fetchone()[0]
    got = engine.basket_summary(cid, "last_3_months")
    assert got["spending"] == pytest.approx(spend, abs=0.01)
    assert sum(b["total"] for b in got["baskets"]) == pytest.approx(spend, abs=0.03)
    assert [b["basket"] for b in got["baskets"]] == ["essentials", "unexpected", "everyday"]


def test_every_spending_row_has_exactly_one_basket():
    assert db.scalar("SELECT count(*) FROM tx WHERE flow = 'spend' AND basket IS NULL") == 0
    assert db.scalar("SELECT count(*) FROM tx WHERE flow <> 'spend' AND basket IS NOT NULL") == 0
    assert set(r["basket"] for r in db.rows("SELECT DISTINCT basket FROM tx WHERE basket IS NOT NULL")) == {
        "essentials",
        "unexpected",
        "everyday",
    }


@pytest.mark.parametrize(
    "where, basket",
    [
        ("tx_type = 'housing_payment'", "essentials"),
        ("tx_type = 'utilities_payment'", "essentials"),
        ("category = 'Groceries'", "essentials"),
        ("category = 'Health'", "unexpected"),
        ("category = 'Home & Tech' AND -amount >= 300", "unexpected"),
        ("category = 'Home & Tech' AND -amount < 300", "everyday"),
        ("mcc = '4121'", "everyday"),
        ("category = 'Transportation' AND mcc = '4111' AND -amount < 300", "essentials"),
        ("category = 'Transportation' AND mcc <> '4121' AND -amount >= 300", "unexpected"),
        ("category IN ('Restaurants', 'Entertainment', 'Lifestyle', 'Travel')", "everyday"),
    ],
)
def test_basket_rules(where, basket):
    found = {r["basket"] for r in db.rows(f"SELECT DISTINCT basket FROM tx WHERE {where}")}
    assert found == {basket}


def test_savings_and_transfers_are_not_spending():
    flows = {r["tx_type"]: r["flow"] for r in db.rows("SELECT DISTINCT tx_type, flow FROM tx")}
    assert flows["investment_deposit"] == "to_savings"
    assert flows["salary_sweep"] == "transfer_out"
    assert flows["salary"] == "income"
    assert flows["purchase"] == "spend"


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_safe_to_spend_adds_up(cid):
    s = engine.safe_to_spend(cid)
    lines = s["budget"]
    budget_index = next(i for i, line in enumerate(lines) if line.get("total"))
    assert sum(line["amount"] for line in lines[:budget_index]) == pytest.approx(lines[budget_index]["amount"], abs=0.05)
    left = lines[-1]["amount"]
    assert lines[budget_index]["amount"] + lines[budget_index + 1]["amount"] == pytest.approx(left, abs=0.02)
    cover = s["balance_check"]["balance_can_cover"]
    assert s["safe_to_spend_until_payday"] == pytest.approx(max(0.0, min(left, cover)), abs=0.02)
    assert s["safe_to_spend_until_payday"] >= 0
    days = s["pay_period"]["days_left"]
    assert s["safe_per_day"] * days == pytest.approx(s["safe_to_spend_until_payday"], abs=0.01 * days + 0.01)
    assert s["this_week"]["safe_to_spend"] <= s["safe_to_spend_until_payday"] + 0.05
    assert s["status"] in {"comfortable", "on_track", "tight", "over_budget", "short"}


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_a_bigger_savings_goal_never_raises_safe_to_spend(cid):
    assert (
        engine.safe_to_spend(cid, savings_goal_pct=30)["safe_to_spend_until_payday"]
        <= engine.safe_to_spend(cid, savings_goal_pct=0)["safe_to_spend_until_payday"]
    )


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_cashflow_income_matches_raw(raw, cid):
    income = raw.execute(
        "SELECT coalesce(sum(amount), 0) FROM raw WHERE customer_id = ? AND tx_type IN ('salary', 'other_income') "
        "AND tx_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'",
        [cid],
    ).fetchone()[0]
    flow = engine.cashflow(cid, 3)
    assert [m["month"] for m in flow["months"]][-1] == "2026-09"
    assert flow["months"][-1]["income"] == pytest.approx(income, abs=0.01)


def test_grouping_by_category_adds_up():
    got = engine.spending("CUST00874", "last_12_months", group_by="category", top=50)
    assert sum(r["total"] for r in got["breakdown"]) == pytest.approx(got["total"], abs=0.05)


def test_unknown_inputs_are_explained():
    with pytest.raises(engine.EngineError):
        engine.customer("CUST99999")
    with pytest.raises(engine.EngineError):
        engine.spending("CUST00001", category="nonsense")
    with pytest.raises(engine.EngineError):
        engine.what_if("CUST00001", "nonsense", -20)
    with pytest.raises(ValueError):
        engine.spending("CUST00001", period="sometime")


def test_periods():
    today = dt.date(2026, 9, 30)  # a Wednesday, and the last day of the month
    assert periods.resolve("last_month", today).start == dt.date(2026, 8, 1)
    assert periods.resolve("last_month", today).end == dt.date(2026, 8, 31)
    assert periods.resolve("this_week", today).start == dt.date(2026, 9, 28)
    assert periods.resolve("this_month", today).days == 30
    assert periods.resolve("2026-02", today).end == dt.date(2026, 2, 28)
    assert periods.resolve("last_3_months", today).start == dt.date(2026, 7, 1)
    assert periods.resolve("last_3_months", dt.date(2026, 9, 29)).end == dt.date(2026, 8, 31)
    assert periods.resolve("last_7_days", today).days == 7
    august = periods.resolve("last_month", today)
    assert august.previous().start == dt.date(2026, 7, 1) and august.previous().end == dt.date(2026, 7, 31)
    assert periods.resolve(None, today, start="2026-01-01", end="2026-12-31").end == today
