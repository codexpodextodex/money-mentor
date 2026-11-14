"""DuckDB database: loads the Parquet files once and derives the working tables.

Tables built at startup:
    tx          every transaction, plus flow, basket and subcategory
    customers   customer_id, postal_code, age, age_band, area
    cust_month  per customer and month: sums by category, subcategory, basket, flow
    cust_avg    per customer: average monthly figures over the last 12 months
    mtg_final   one row per mortgage application (outcome)
    mtg_events  mortgage negotiation events
"""

from __future__ import annotations

import datetime as dt
import threading

import duckdb

from . import baskets, config

_lock = threading.Lock()
_base: duckdb.DuckDBPyConnection | None = None
_local = threading.local()
_today: dt.date | None = None


def _path(name: str) -> str:
    path = config.DATA_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Build the data first: python scripts/build_data.py --src <csv folder>"
        )
    return str(path).replace("\\", "/").replace("'", "''")


def _build() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        f"""
        CREATE TABLE tx AS
        SELECT
            customer_id, tx_date, tx_ts, category, amount, balance_after, tx_type, merchant_id, mcc,
            {baskets.subcategory_sql()} AS subcategory,
            {baskets.FLOW_SQL} AS flow,
            {baskets.BASKET_SQL} AS basket
        FROM read_parquet('{_path("tx")}')
        ORDER BY customer_id, tx_ts
        """
    )
    con.execute(
        f"""
        CREATE TABLE customers AS
        SELECT
            customer_id, postal_code, age,
            CASE
                WHEN age < 25 THEN 'under 25'
                WHEN age < 35 THEN '25-34'
                WHEN age < 45 THEN '35-44'
                WHEN age < 55 THEN '45-54'
                WHEN age < 65 THEN '55-64'
                ELSE '65 and over'
            END AS age_band,
            CASE substr(postal_code, 1, 2)
                WHEN '00' THEN 'Helsinki'
                WHEN '01' THEN 'Vantaa'
                WHEN '02' THEN 'Espoo'
                ELSE 'Other'
            END AS area
        FROM read_parquet('{_path("customers")}')
        """
    )
    con.execute(f"CREATE TABLE mtg_final AS SELECT * FROM read_parquet('{_path('mtg_final')}')")
    con.execute(f"CREATE TABLE mtg_events AS SELECT * FROM read_parquet('{_path('mtg_events')}')")
    con.execute(
        """
        CREATE TABLE cust_month AS
        SELECT
            customer_id,
            CAST(date_trunc('month', tx_date) AS DATE) AS month,
            flow, basket, category, subcategory,
            sum(amount) AS amount,
            count(*) AS n
        FROM tx
        GROUP BY ALL
        """
    )
    today = con.execute("SELECT max(tx_date) FROM tx").fetchone()[0]
    if config.TODAY_OVERRIDE:
        today = dt.date.fromisoformat(config.TODAY_OVERRIDE)
    global _today
    _today = today

    # Average monthly figures over the 12 complete months ending with the
    # current month (or the previous one when the current month is not over).
    last = _last_complete_month(today)
    first = _add_months(last, -11)
    con.execute(
        """
        CREATE TABLE cust_avg AS
        SELECT
            customer_id,
            sum(amount) FILTER (WHERE flow = 'income') / 12.0 AS income,
            -sum(amount) FILTER (WHERE flow = 'spend') / 12.0 AS spend,
            coalesce(-sum(amount) FILTER (WHERE basket = 'essentials'), 0) / 12.0 AS essentials,
            coalesce(-sum(amount) FILTER (WHERE basket = 'unexpected'), 0) / 12.0 AS unexpected,
            coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) / 12.0 AS everyday,
            coalesce(-sum(amount) FILTER (WHERE flow = 'to_savings'), 0) / 12.0 AS to_savings,
            coalesce(sum(amount) FILTER (WHERE flow = 'from_savings'), 0) / 12.0 AS from_savings,
            coalesce(-sum(amount) FILTER (WHERE flow = 'transfer_out'), 0) / 12.0 AS transfer_out
        FROM cust_month
        WHERE month BETWEEN ? AND ?
        GROUP BY customer_id
        """,
        [first, last],
    )
    # Habits per customer over the same 12 months, used for the spender
    # profile and for comparing a customer with their peers.
    window_end = _add_months(last, 1) - dt.timedelta(days=1)
    con.execute(
        f"""
        CREATE TABLE cust_features AS
        WITH t AS (SELECT * FROM tx WHERE tx_date BETWEEN ? AND ?),
        m AS (
            SELECT customer_id, date_trunc('month', tx_date) AS month,
                coalesce(sum(amount) FILTER (WHERE flow = 'income'), 0) AS income,
                coalesce(-sum(amount) FILTER (WHERE flow = 'spend'), 0) AS spend,
                coalesce(-sum(amount) FILTER (WHERE flow = 'transfer_out'), 0) AS transfer_out,
                coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) AS everyday
            FROM t GROUP BY 1, 2
        ),
        ma AS (
            SELECT customer_id,
                count(*) FILTER (WHERE income - spend - transfer_out < 0) AS negative_months,
                stddev_pop(everyday) / nullif(avg(everyday), 0) AS everyday_cv
            FROM m GROUP BY 1
        ),
        a AS (
            SELECT customer_id,
                count(*) FILTER (WHERE basket = 'everyday' AND -amount < {baskets.SMALL_PURCHASE_EUR}) / 52.0 AS small_per_week,
                coalesce(-sum(amount) FILTER (WHERE basket = 'everyday' AND -amount < {baskets.SMALL_PURCHASE_EUR}), 0) / 12.0 AS small_monthly,
                coalesce(-sum(amount) FILTER (WHERE basket = 'everyday' AND -amount >= {baskets.BIG_PURCHASE_EUR}), 0) AS big_everyday,
                coalesce(-sum(amount) FILTER (WHERE basket = 'everyday' AND dayofweek(tx_date) IN (0, 6)), 0) AS weekend_everyday,
                coalesce(-sum(amount) FILTER (WHERE category = 'Restaurants'), 0) AS restaurants,
                count(DISTINCT tx_date) FILTER (WHERE balance_after < 0) AS overdraft_days
            FROM t GROUP BY 1
        )
        SELECT
            c.*,
            (c.income - c.spend - c.transfer_out) / nullif(c.income, 0) AS savings_rate,
            c.essentials / nullif(c.income, 0) AS essentials_of_income,
            c.everyday / nullif(c.spend, 0) AS everyday_share,
            a.small_per_week,
            a.small_monthly,
            a.big_everyday / nullif(c.everyday * 12, 0) AS big_ticket_share,
            a.weekend_everyday / nullif(c.everyday * 12, 0) AS weekend_share,
            a.restaurants / nullif(c.everyday * 12, 0) AS restaurants_share,
            a.overdraft_days,
            ma.negative_months,
            ma.everyday_cv
        FROM cust_avg c JOIN a USING (customer_id) JOIN ma USING (customer_id)
        """,
        [first, window_end],
    )
    con.execute("CREATE INDEX tx_customer ON tx (customer_id)")
    return con


def _add_months(first_of_month: dt.date, n: int) -> dt.date:
    index = first_of_month.year * 12 + (first_of_month.month - 1) + n
    return dt.date(index // 12, index % 12 + 1, 1)


def _last_complete_month(today: dt.date) -> dt.date:
    """First day of the most recent month that is fully in the data."""
    this_month = today.replace(day=1)
    next_month = _add_months(this_month, 1)
    is_last_day = today == next_month - dt.timedelta(days=1)
    return this_month if is_last_day else _add_months(this_month, -1)


def init() -> None:
    """Build the database if it is not built yet."""
    global _base
    with _lock:
        if _base is None:
            _base = _build()


def cursor() -> duckdb.DuckDBPyConnection:
    """A cursor for the calling thread."""
    init()
    cur = getattr(_local, "cur", None)
    if cur is None:
        cur = _base.cursor()
        _local.cur = cur
    return cur


def today() -> dt.date:
    """The day the app treats as today (the last day in the data by default)."""
    init()
    return _today


def last_complete_month() -> dt.date:
    return _last_complete_month(today())


def add_months(first_of_month: dt.date, n: int) -> dt.date:
    return _add_months(first_of_month, n)


def rows(sql: str, params: list | tuple = ()) -> list[dict]:
    cur = cursor()
    res = cur.execute(sql, list(params))
    names = [d[0] for d in res.description]
    return [dict(zip(names, r)) for r in res.fetchall()]


def row(sql: str, params: list | tuple = ()) -> dict | None:
    result = rows(sql, params)
    return result[0] if result else None


def scalar(sql: str, params: list | tuple = ()):
    cur = cursor()
    found = cur.execute(sql, list(params)).fetchone()
    return found[0] if found else None
