"""Your year, replayed: checked against independent SQL over the raw Parquet file."""

import duckdb
import pytest

from app import config, db, engine, offline, replay, tools

CUSTOMERS = ["CUST00086", "CUST00874", "CUST00728", "CUST02396", "CUST00001"]
EVERYDAY = (
    "tx_type = 'purchase' AND (category IN ('Restaurants', 'Entertainment', 'Lifestyle', 'Travel') "
    "OR (category = 'Home & Tech' AND -amount < 300) OR mcc = '4121')"
)
YEAR = "tx_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'"


@pytest.fixture(scope="module")
def raw():
    path = str(config.DATA_DIR / "tx.parquet").replace("\\", "/")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW raw AS SELECT * FROM read_parquet('{path}')")
    return con


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_everyday_less_is_a_fifth_of_everyday_spending(raw, cid):
    everyday = raw.execute(
        f"SELECT coalesce(-sum(amount), 0) FROM raw WHERE customer_id = ? AND {YEAR} AND {EVERYDAY}", [cid]
    ).fetchone()[0]
    got = replay.replay(cid, "everyday_less")
    assert got["period"]["start"] == "2025-10-01" and got["period"]["end"] == "2026-09-30"
    assert got["shown"]["kept_over_the_year"] == pytest.approx(0.2 * everyday, abs=0.02)


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_what_happened_matches_raw(raw, cid):
    days, lowest = raw.execute(
        f"SELECT count(DISTINCT tx_date) FILTER (WHERE balance_after < 0), min(balance_after) FROM raw WHERE customer_id = ? AND {YEAR}",
        [cid],
    ).fetchone()
    end = raw.execute(
        f"SELECT arg_max(balance_after, tx_timestamp_sort) FROM (SELECT balance_after, tx_ts AS tx_timestamp_sort FROM raw WHERE customer_id = ? AND {YEAR})",
        [cid],
    ).fetchone()[0]
    got = replay.replay(cid)
    assert got["what_happened"]["days_below_zero"] == days
    assert got["what_happened"]["lowest_balance"] == pytest.approx(lowest, abs=0.01)
    assert got["what_happened"]["balance_today"] == pytest.approx(end, abs=0.01)


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_replay_is_consistent(cid):
    got = replay.replay(cid)
    levers = got["levers"]
    assert 1 <= len(levers) <= 3
    kept = [entry["kept_over_the_year"] for entry in levers]
    assert kept == sorted(kept, reverse=True)
    assert got["shown"]["lever"] == levers[0]["lever"]
    for entry in levers:
        # money kept only ever raises the balance, so nothing can get worse
        assert entry["balance_today"]["after"] == pytest.approx(entry["balance_today"]["before"] + entry["kept_over_the_year"], abs=0.02)
        assert entry["days_below_zero"]["after"] <= entry["days_below_zero"]["before"]
        assert entry["lowest_balance"]["after"] >= entry["lowest_balance"]["before"] - 0.01
        assert entry["kept_over_the_year"] >= 0
    series = got["series"]
    assert len(series["week_starts"]) == len(series["lowest_balance_each_week"]) == len(series["with_the_change"])
    assert all(a <= b for a, b in zip(series["lowest_balance_each_week"], series["with_the_change"]))
    assert "not a forecast" in got["how_to_read"]


def test_weekly_rhythm_only_trims_the_heaviest_weeks():
    got = replay.replay("CUST00086", "weekly_rhythm")
    cap = got["normal_busy_week"]
    assert cap >= got["usual_everyday_week"]
    weekly = db.rows(
        "SELECT date_trunc('week', tx_date) AS week, -sum(amount) AS total FROM tx "
        "WHERE customer_id = 'CUST00086' AND basket = 'everyday' AND tx_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30' GROUP BY 1"
    )
    expected = sum(max(0.0, w["total"] - cap) for w in weekly)
    assert got["shown"]["kept_over_the_year"] == pytest.approx(expected, abs=0.05)
    assert got["plan"]["weekly_everyday_allowance"] == cap
    # at most a quarter of the year's weeks are touched
    assert sum(1 for w in weekly if w["total"] > cap) <= 14


def test_the_year_before_is_reported():
    got = replay.replay("CUST00086")
    hold = got["does_it_hold"]
    assert hold["year_before"] == {"start": "2024-10-01", "end": "2025-09-30"}
    assert isinstance(hold["top_lever_was_also_top_the_year_before"], bool)
    assert 1 <= hold["this_lever_rank_the_year_before"] <= len(replay.LEVERS)
    assert all("year_before" in entry for entry in got["levers"])


def test_levers_are_personal():
    """Different customers get different top levers: that is the point."""
    tops = {replay.replay(r["customer_id"])["shown"]["lever"] for r in db.rows("SELECT customer_id FROM customers USING SAMPLE 150 ROWS (reservoir, 4)")}
    assert len(tops) >= 3


def test_bad_lever_and_tool_wiring():
    with pytest.raises(engine.EngineError):
        replay.replay("CUST00086", "magic")
    assert "error" in tools.call("CUST00086", "replay_year", {"lever": "magic"})
    assert tools.call("CUST00086", "replay_year", {"lever": "small_purchases"})["shown"]["lever"] == "small_purchases"
    assert offline.route("How could I save more?") == ("replay_year", {})
    events = list(offline.run("CUST00086", "What would have helped me most?"))
    assert "not a forecast" in events[-1]["text"]
