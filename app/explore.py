"""MyData explore mode: free SQL over your own transactions, and only yours.

The customer (or the model on their behalf) can run any SELECT. Safety does
not rely on inspecting the query text. Each query runs in a separate
in-memory database that holds nothing but that one customer's rows, with
file and network access switched off, a row limit and a time limit.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

import duckdb

from . import db
from .engine import EngineError, customer

MAX_ROWS = 200
TIMEOUT_S = 3.0
_CACHE_SIZE = 16

SCHEMA = [
    ("date", "DATE", "day of the transaction"),
    ("time", "TIMESTAMP", "exact time"),
    ("amount", "DOUBLE", "euros, negative = money out, positive = money in"),
    ("spent", "DOUBLE", "euros spent as a positive number, 0 for money in"),
    ("category", "VARCHAR", "e.g. Groceries, Restaurants, Housing, Salary"),
    ("subcategory", "VARCHAR", "e.g. Taxis, Supermarkets, Fast food, Utility bills"),
    ("basket", "VARCHAR", "essentials, unexpected or everyday; NULL when not spending"),
    ("flow", "VARCHAR", "spend, income, to_savings, from_savings or transfer_out"),
    ("type", "VARCHAR", "purchase, housing_payment, utilities_payment, salary, ..."),
    ("merchant_id", "VARCHAR", "synthetic merchant id for card purchases"),
    ("mcc", "VARCHAR", "merchant category code for card purchases"),
    ("balance_after", "DOUBLE", "account balance after the transaction"),
]

_lock = threading.Lock()
_sandboxes: "OrderedDict[str, duckdb.DuckDBPyConnection]" = OrderedDict()


def schema() -> dict:
    return {
        "table": "my_transactions",
        "columns": [{"name": n, "type": t, "meaning": m} for n, t, m in SCHEMA],
        "dialect": "DuckDB SQL",
        "example": "SELECT subcategory, round(sum(spent), 2) AS total FROM my_transactions WHERE basket = 'everyday' GROUP BY 1 ORDER BY 2 DESC",
    }


def _sandbox(cid: str) -> duckdb.DuckDBPyConnection:
    with _lock:
        if cid in _sandboxes:
            _sandboxes.move_to_end(cid)
            return _sandboxes[cid]
    found = db.cursor().execute(
        """
        SELECT tx_date, tx_ts, amount, CASE WHEN amount < 0 THEN -amount ELSE 0 END, category, subcategory,
               basket, flow, tx_type, merchant_id, mcc, balance_after
        FROM tx WHERE customer_id = ? ORDER BY tx_ts
        """,
        [cid],
    ).fetchall()
    con = duckdb.connect(":memory:")
    columns = ", ".join(f'"{name}" {kind}' for name, kind, _ in SCHEMA)
    con.execute(f"CREATE TABLE my_transactions ({columns})")
    if found:
        con.executemany(f"INSERT INTO my_transactions VALUES ({', '.join('?' for _ in SCHEMA)})", found)
    # Lock the sandbox down: no files, no network, no changing these settings.
    con.execute("SET enable_external_access = false")
    con.execute("SET threads = 1")
    con.execute("SET memory_limit = '256MB'")
    con.execute("SET lock_configuration = true")
    with _lock:
        _sandboxes[cid] = con
        while len(_sandboxes) > _CACHE_SIZE:
            _, old = _sandboxes.popitem(last=False)
            old.close()
    return con


def run(customer_id: str, sql: str) -> dict:
    """Run one read-only query over the customer's own transactions."""
    cid = customer(customer_id)["customer_id"]
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise EngineError("Write a SELECT query over the table my_transactions.")
    con = _sandbox(cid)
    try:
        statements = con.extract_statements(text)
    except duckdb.Error as exc:
        raise EngineError(f"SQL error: {exc}") from exc
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        raise EngineError("Only a single SELECT query is allowed.")

    cur = con.cursor()
    timer = threading.Timer(TIMEOUT_S, cur.interrupt)
    timer.start()
    try:
        res = cur.execute(f"SELECT * FROM ({text}) AS q LIMIT {MAX_ROWS + 1}")
        names = [d[0] for d in res.description]
        fetched = res.fetchall()
    except duckdb.InterruptException as exc:
        raise EngineError(f"The query took longer than {TIMEOUT_S:g} seconds and was stopped.") from exc
    except duckdb.Error as exc:
        raise EngineError(f"SQL error: {str(exc).splitlines()[0]}") from exc
    finally:
        timer.cancel()
        cur.close()

    truncated = len(fetched) > MAX_ROWS
    rows = [
        [round(v, 2) if isinstance(v, float) else (v.isoformat() if hasattr(v, "isoformat") else v) for v in r]
        for r in fetched[:MAX_ROWS]
    ]
    return {
        "customer_id": cid,
        "sql": text,
        "columns": names,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
