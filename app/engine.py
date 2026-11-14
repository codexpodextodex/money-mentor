"""The money engine.

Every number the coach says is computed here, with plain SQL over the
customer's own transactions. The language model never does arithmetic: it
chooses one of these functions, and explains the result.

All functions take a customer_id and return JSON-ready dicts.
"""

from __future__ import annotations

import calendar
import datetime as dt
import statistics
from functools import lru_cache

from . import baskets, db, periods


class EngineError(ValueError):
    """A problem the user (or the model) can fix: unknown customer, bad filter."""


# ---------------------------------------------------------------- helpers ---


def _r(value, digits: int = 2):
    return None if value is None else round(float(value), digits)


def _pct(part, whole, digits: int = 1):
    if not whole:
        return None
    return round(100.0 * float(part) / float(whole), digits)


def customer(customer_id: str) -> dict:
    found = db.row("SELECT * FROM customers WHERE customer_id = ?", [str(customer_id).strip().upper()])
    if not found:
        raise EngineError(f"Unknown customer '{customer_id}'.")
    return found


@lru_cache(maxsize=1)
def data_start() -> dt.date:
    return db.scalar("SELECT min(tx_date) FROM tx")


@lru_cache(maxsize=1)
def subcategories() -> dict[str, str]:
    """Spending subcategory -> its category."""
    found = db.rows("SELECT DISTINCT subcategory, category FROM tx WHERE flow = 'spend' ORDER BY 2, 1")
    return {r["subcategory"]: r["category"] for r in found}


CATEGORY_ALIASES = {
    "rent": "Housing",
    "home": "Housing",
    "bills": "Utilities",
    "utility": "Utilities",
    "utility bills": "Utilities",
    "food": "Groceries",
    "grocery": "Groceries",
    "transport": "Transportation",
    "restaurant": "Restaurants",
    "dining": "Restaurants",
    "dining out": "Restaurants",
    "eating out": "Restaurants",
    "home and tech": "Home & Tech",
    "home tech": "Home & Tech",
    "shopping": "Lifestyle",
    "fun": "Entertainment",
    "trips": "Travel",
}

SUBCATEGORY_ALIASES = {
    "taxi": ["Taxis"],
    "cab": ["Taxis"],
    "cabs": ["Taxis"],
    "fuel": ["Service stations", "Fuel pumps"],
    "petrol": ["Service stations", "Fuel pumps"],
    "gas": ["Service stations", "Fuel pumps"],
    "pharmacy": ["Pharmacies"],
    "bars": ["Bars and pubs"],
    "bar": ["Bars and pubs"],
    "pubs": ["Bars and pubs"],
    "flights": ["Airlines"],
    "flight": ["Airlines"],
    "hotel": ["Hotels"],
    "doctor": ["Doctors"],
    "dentist": ["Dentists"],
    "cinema": ["Cinemas"],
    "movies": ["Cinemas"],
    "clothes": ["Family clothing", "Clothing stores"],
    "clothing": ["Family clothing", "Clothing stores"],
    "clothes shops": ["Family clothing", "Clothing stores"],
    # The data has one kind of bill, "Utility bills": it does not say which utility.
    "electricity": ["Utility bills"],
    "electricity bill": ["Utility bills"],
    "power": ["Utility bills"],
    "water": ["Utility bills"],
    "internet": ["Utility bills"],
    "phone bill": ["Utility bills"],
    "utilities": ["Utility bills"],
    "sähkö": ["Utility bills"],
    "sähkölasku": ["Utility bills"],
    "el": ["Utility bills"],
    "elräkning": ["Utility bills"],
    "burgers": ["Fast food"],
    "burger": ["Fast food"],
    "takeaway": ["Fast food"],
    "take away": ["Fast food"],
    "junk food": ["Fast food"],
    "pubs and bars": ["Bars and pubs"],
    "drinks": ["Bars and pubs"],
    "electronics": ["Electronics"],
    "gadgets": ["Electronics"],
    "parking": ["Parking"],
    "public transport": ["Public transport"],
    "tickets": ["Theatre and tickets"],
    # Finnish and Swedish everyday words, for when the model passes the customer's own word.
    "pikaruoka": ["Fast food"],
    "snabbmat": ["Fast food"],
    "vaatteet": ["Family clothing", "Clothing stores"],
    "kläder": ["Family clothing", "Clothing stores"],
    "taksi": ["Taxis"],
    "taksit": ["Taxis"],
    "polttoaine": ["Service stations", "Fuel pumps"],
    "bensa": ["Service stations", "Fuel pumps"],
    "bensin": ["Service stations", "Fuel pumps"],
    "apteekki": ["Pharmacies"],
    "apotek": ["Pharmacies"],
    "baarit": ["Bars and pubs"],
    "barer": ["Bars and pubs"],
    "supermarket": ["Supermarkets"],
    "books": ["Book stores"],
    "sports": ["Sporting goods"],
    "bus": ["Public transport"],
    "train": ["Public transport"],
    "metro": ["Public transport"],
}

BASKET_ALIASES = {
    "essentials": "essentials",
    "regular": "essentials",
    "regular essentials": "essentials",
    "mandatory regular": "essentials",
    "fixed": "essentials",
    "unexpected": "unexpected",
    "unexpected necessities": "unexpected",
    "irregular": "unexpected",
    "mandatory irregular": "unexpected",
    "surprises": "unexpected",
    "everyday": "everyday",
    "everyday spending": "everyday",
    "discretionary": "everyday",
    "leaks": "everyday",
}


def _norm(text: str) -> str:
    return " ".join(str(text).strip().lower().replace("_", " ").replace("&", "and").split())


def _match_category(value: str) -> str | None:
    key = _norm(value)
    for name in baskets.SPEND_CATEGORIES:
        if _norm(name) == key:
            return name
    return CATEGORY_ALIASES.get(key)


def _match_subcategories(value: str) -> list[str] | None:
    key = _norm(value)
    for name in subcategories():
        if _norm(name) == key:
            return [name]
    if key in SUBCATEGORY_ALIASES:
        return SUBCATEGORY_ALIASES[key]
    singular = key[:-1] if key.endswith("s") else key
    for name in subcategories():
        if _norm(name).rstrip("s") == singular:
            return [name]
    return None


def resolve_target(value: str) -> dict:
    """Work out whether a word names a basket, a category or a subcategory."""
    key = _norm(value)
    if key in BASKET_ALIASES:
        b = BASKET_ALIASES[key]
        return {"type": "basket", "values": [b], "label": baskets.BASKETS[b]["name"]}
    category = _match_category(value)
    if category:
        return {"type": "category", "values": [category], "label": category}
    subs = _match_subcategories(value)
    if subs:
        return {"type": "subcategory", "values": subs, "label": " and ".join(subs)}
    options = ", ".join(baskets.SPEND_CATEGORIES)
    raise EngineError(
        f"'{value}' is not a basket, category or subcategory I know. Categories: {options}. "
        f"Baskets: essentials, unexpected, everyday. Subcategories include: {', '.join(list(subcategories())[:12])}..."
    )


def _filters(category=None, subcategory=None, basket=None, merchant_id=None, min_amount=None, max_amount=None):
    """Build the WHERE fragment for optional spending filters."""
    where, params, shown = [], [], {}
    if basket:
        key = BASKET_ALIASES.get(_norm(basket))
        if not key:
            raise EngineError("basket must be one of: essentials, unexpected, everyday.")
        where.append("basket = ?")
        params.append(key)
        shown["basket"] = baskets.BASKETS[key]["name"]
    if category:
        name = _match_category(category)
        if name:
            where.append("category = ?")
            params.append(name)
            shown["category"] = name
        elif not subcategory and _match_subcategories(category):
            subcategory = category  # the caller put a subcategory in the category slot
        else:
            raise EngineError(f"Unknown category '{category}'. Categories: {', '.join(baskets.SPEND_CATEGORIES)}.")
    if subcategory:
        subs = _match_subcategories(subcategory)
        if not subs:
            raise EngineError(
                f"Unknown subcategory '{subcategory}'. Known: {', '.join(subcategories())}."
            )
        where.append(f"subcategory IN ({', '.join('?' for _ in subs)})")
        params.extend(subs)
        shown["subcategory"] = " and ".join(subs)
    if merchant_id:
        where.append("merchant_id = ?")
        params.append(str(merchant_id).strip().upper())
        shown["merchant_id"] = str(merchant_id).strip().upper()
    if min_amount is not None:
        where.append("-amount >= ?")
        params.append(float(min_amount))
        shown["min_amount"] = float(min_amount)
    if max_amount is not None:
        where.append("-amount <= ?")
        params.append(float(max_amount))
        shown["max_amount"] = float(max_amount)
    sql = "".join(f" AND {w}" for w in where)
    return sql, params, shown


def _clamp(period: periods.Period) -> periods.Period:
    start = max(period.start, data_start())
    return periods.Period(start, period.end, period.label) if start != period.start else period


GROUPINGS = {
    "category": "category",
    "subcategory": "subcategory",
    "basket": "basket",
    "merchant": "coalesce(merchant_id, subcategory)",
    "month": "strftime(tx_date, '%Y-%m')",
    "week": "strftime(date_trunc('week', tx_date), '%Y-%m-%d')",
    "weekday": "dayname(tx_date)",
    "day": "strftime(tx_date, '%Y-%m-%d')",
}
TIME_GROUPINGS = {"month", "week", "day"}
COUNTED_SHOWN = 12  # how many of the counted payments a filtered total carries along
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --------------------------------------------------------------- spending ---


def spending(
    customer_id: str,
    period: str | None = "last_month",
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    basket: str | None = None,
    merchant_id: str | None = None,
    group_by: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    top: int = 8,
) -> dict:
    """Total spending in a period, optionally filtered and broken down."""
    cid = customer(customer_id)["customer_id"]
    p = _clamp(periods.resolve(period, db.today(), start, end))
    where, params, shown = _filters(category, subcategory, basket, merchant_id, min_amount, max_amount)
    base = f"FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ?{where}"
    args = [cid, p.start, p.end, *params]

    totals = db.row(
        f"SELECT coalesce(-sum(amount), 0) AS total, count(*) AS n, coalesce(max(-amount), 0) AS largest {base}", args
    )
    all_spend = db.scalar(
        "SELECT coalesce(-sum(amount), 0) FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ?",
        [cid, p.start, p.end],
    )
    result = {
        "customer_id": cid,
        "period": p.as_dict(),
        "filters": shown,
        "total": _r(totals["total"]),
        "transactions": totals["n"],
        "average_per_transaction": _r(totals["total"] / totals["n"]) if totals["n"] else 0.0,
        "largest_transaction": _r(totals["largest"]),
        "share_of_all_spending_pct": _pct(totals["total"], all_spend) if shown else 100.0,
    }
    if p.days >= 45:
        result["monthly_average"] = _r(totals["total"] / p.months)
    if shown and totals["n"]:
        # The payments behind a filtered total, newest first, so the app can show what was counted.
        counted = db.rows(
            f"SELECT tx_date, category, subcategory, basket, -amount AS amount {base} ORDER BY tx_ts DESC LIMIT {COUNTED_SHOWN}",
            args,
        )
        result["counted"] = {
            "shown": len(counted),
            "of": totals["n"],
            "payments": [
                {
                    "date": r["tx_date"].isoformat(),
                    "amount": _r(r["amount"]),
                    "category": r["category"],
                    "subcategory": r["subcategory"],
                    "basket": baskets.BASKETS[r["basket"]]["name"],
                }
                for r in counted
            ],
        }

    prev = p.previous()
    if prev.start >= data_start():
        prev_total = db.scalar(
            f"SELECT coalesce(-sum(amount), 0) {base}", [cid, prev.start, prev.end, *params]
        )
        result["previous_period"] = {
            "start": prev.start.isoformat(),
            "end": prev.end.isoformat(),
            "total": _r(prev_total),
            "change": _r(totals["total"] - prev_total),
            "change_pct": _pct(totals["total"] - prev_total, prev_total),
        }

    if group_by:
        key = _norm(group_by)
        if key not in GROUPINGS:
            raise EngineError(f"group_by must be one of: {', '.join(GROUPINGS)}.")
        expr = GROUPINGS[key]
        order = "1" if key in TIME_GROUPINGS else "2 DESC"
        found = db.rows(
            f"SELECT {expr} AS key, -sum(amount) AS total, count(*) AS n {base} GROUP BY 1 ORDER BY {order}", args
        )
        if key == "weekday":
            found.sort(key=lambda r: WEEKDAYS.index(r["key"]))
        elif key == "basket":
            found.sort(key=lambda r: baskets.BASKET_ORDER.index(r["key"]))
        limit = None if key in TIME_GROUPINGS or key in ("weekday", "basket") else max(1, int(top))
        shown_rows = found if limit is None else found[:limit]
        result["group_by"] = key
        result["breakdown"] = [
            {
                "key": baskets.BASKETS[r["key"]]["name"] if key == "basket" else r["key"],
                "total": _r(r["total"]),
                "transactions": r["n"],
                "share_pct": _pct(r["total"], totals["total"]),
            }
            for r in shown_rows
        ]
        if limit is not None and len(found) > limit:
            rest = found[limit:]
            result["breakdown"].append(
                {
                    "key": f"{len(rest)} more",
                    "total": _r(sum(r["total"] for r in rest)),
                    "transactions": sum(r["n"] for r in rest),
                    "share_pct": _pct(sum(r["total"] for r in rest), totals["total"]),
                }
            )
    return result


def transactions(
    customer_id: str,
    period: str | None = "last_30_days",
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    basket: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    sort: str = "date",
    limit: int = 15,
) -> dict:
    """List individual payments, newest or largest first."""
    cid = customer(customer_id)["customer_id"]
    p = _clamp(periods.resolve(period, db.today(), start, end))
    where, params, shown = _filters(category, subcategory, basket, None, min_amount, max_amount)
    order = "-amount DESC" if _norm(sort) in ("amount", "largest", "size") else "tx_ts DESC"
    limit = max(1, min(int(limit), 50))
    base = f"FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ?{where}"
    args = [cid, p.start, p.end, *params]
    found = db.rows(
        f"SELECT tx_date, category, subcategory, basket, -amount AS amount, merchant_id {base} ORDER BY {order} LIMIT {limit}",
        args,
    )
    totals = db.row(f"SELECT count(*) AS n, coalesce(-sum(amount), 0) AS total {base}", args)
    count = totals["n"]
    return {
        "customer_id": cid,
        "period": p.as_dict(),
        "filters": shown,
        "matching_transactions": count,
        "total": _r(totals["total"]),
        "shown": len(found),
        "sorted_by": "amount" if order.startswith("-amount") else "date",
        "transactions": [
            {
                "date": r["tx_date"].isoformat(),
                "amount": _r(r["amount"]),
                "category": r["category"],
                "subcategory": r["subcategory"],
                "basket": baskets.BASKETS[r["basket"]]["name"],
                "merchant_id": r["merchant_id"],
            }
            for r in found
        ],
    }


# ---------------------------------------------------------------- baskets ---


def basket_summary(customer_id: str, period: str | None = "last_3_months", start: str | None = None, end: str | None = None) -> dict:
    """Where the money went, as the three baskets."""
    cid = customer(customer_id)["customer_id"]
    p = _clamp(periods.resolve(period, db.today(), start, end))
    args = [cid, p.start, p.end]
    by_sub = db.rows(
        """
        SELECT basket, subcategory, -sum(amount) AS total, count(*) AS n
        FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ?
        GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        args,
    )
    flows = db.row(
        """
        SELECT
            coalesce(sum(amount) FILTER (WHERE flow = 'income'), 0) AS income,
            coalesce(-sum(amount) FILTER (WHERE flow = 'spend'), 0) AS spend,
            coalesce(-sum(amount) FILTER (WHERE flow = 'to_savings'), 0) AS to_savings,
            coalesce(-sum(amount) FILTER (WHERE flow = 'transfer_out'), 0) AS transfer_out
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
        """,
        args,
    )
    small = db.row(
        f"""
        SELECT count(*) AS n, coalesce(-sum(amount), 0) AS total
        FROM tx WHERE customer_id = ? AND basket = 'everyday' AND tx_date BETWEEN ? AND ?
          AND -amount < {baskets.SMALL_PURCHASE_EUR}
        """,
        args,
    )
    surprises = db.rows(
        """
        SELECT tx_date, subcategory, -amount AS amount
        FROM tx WHERE customer_id = ? AND basket = 'unexpected' AND tx_date BETWEEN ? AND ?
        ORDER BY -amount DESC LIMIT 3
        """,
        args,
    )
    monthly = p.days >= 45
    out_baskets = []
    for key in baskets.BASKET_ORDER:
        rows = [r for r in by_sub if r["basket"] == key]
        total = sum(r["total"] for r in rows)
        entry = {
            "basket": key,
            "name": baskets.BASKETS[key]["name"],
            "emoji": baskets.BASKETS[key]["emoji"],
            "meaning": baskets.BASKETS[key]["meaning"],
            "total": _r(total),
            "share_of_spending_pct": _pct(total, flows["spend"]) or 0.0,
            "share_of_income_pct": _pct(total, flows["income"]),
            "transactions": sum(r["n"] for r in rows),
            "top": [
                {"subcategory": r["subcategory"], "total": _r(r["total"]), "transactions": r["n"]} for r in rows[:4]
            ],
        }
        if monthly:
            entry["monthly_average"] = _r(total / p.months)
        out_baskets.append(entry)
    result = {
        "customer_id": cid,
        "period": p.as_dict(),
        "income": _r(flows["income"]),
        "spending": _r(flows["spend"]),
        "moved_to_savings": _r(flows["to_savings"]),
        "transferred_to_other_accounts": _r(flows["transfer_out"]),
        "left_over": _r(flows["income"] - flows["spend"] - flows["to_savings"] - flows["transfer_out"]),
        "baskets": out_baskets,
        "small_everyday_purchases": {
            "under_eur": baskets.SMALL_PURCHASE_EUR,
            "count": small["n"],
            "total": _r(small["total"]),
            "per_week": _r(small["n"] / (p.days / 7.0), 1),
        },
        "largest_unexpected": [
            {"date": r["tx_date"].isoformat(), "what": r["subcategory"], "amount": _r(r["amount"])} for r in surprises
        ],
    }
    if monthly:
        result["monthly_income"] = _r(flows["income"] / p.months)
        result["monthly_spending"] = _r(flows["spend"] / p.months)
    return result


def basket_rules() -> dict:
    """The classification rules, for showing to the user."""
    return {
        "baskets": [
            {"basket": k, **{f: baskets.BASKETS[k][f] for f in ("name", "emoji", "meaning", "examples")}}
            for k in baskets.BASKET_ORDER
        ],
        "rules": baskets.RULES_TEXT,
    }


# --------------------------------------------------------------- cashflow ---


def cashflow(customer_id: str, months: int = 6) -> dict:
    """Month by month: money in, the three baskets, savings, and the balance."""
    cid = customer(customer_id)["customer_id"]
    months = max(1, min(int(months), 24))
    p = periods.complete_months(db.today(), months)
    found = db.rows(
        """
        SELECT
            strftime(date_trunc('month', tx_date), '%Y-%m') AS month,
            coalesce(sum(amount) FILTER (WHERE flow = 'income'), 0) AS income,
            coalesce(-sum(amount) FILTER (WHERE basket = 'essentials'), 0) AS essentials,
            coalesce(-sum(amount) FILTER (WHERE basket = 'unexpected'), 0) AS unexpected,
            coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) AS everyday,
            coalesce(-sum(amount) FILTER (WHERE flow = 'to_savings'), 0) AS to_savings,
            coalesce(sum(amount) FILTER (WHERE flow = 'from_savings'), 0) AS from_savings,
            coalesce(-sum(amount) FILTER (WHERE flow = 'transfer_out'), 0) AS transfer_out,
            arg_max(balance_after, tx_ts) AS end_balance,
            min(balance_after) AS lowest_balance
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 1
        """,
        [cid, p.start, p.end],
    )
    rows = []
    for r in found:
        spend = r["essentials"] + r["unexpected"] + r["everyday"]
        rows.append(
            {
                "month": r["month"],
                "income": _r(r["income"]),
                "essentials": _r(r["essentials"]),
                "unexpected": _r(r["unexpected"]),
                "everyday": _r(r["everyday"]),
                "spending": _r(spend),
                "to_savings": _r(r["to_savings"]),
                "transfer_out": _r(r["transfer_out"]),
                "net": _r(r["income"] - spend),
                "end_balance": _r(r["end_balance"]),
                "lowest_balance": _r(r["lowest_balance"]),
            }
        )
    n = len(rows) or 1
    return {
        "customer_id": cid,
        "period": p.as_dict(),
        "months": rows,
        "average": {
            key: _r(sum(r[key] for r in rows) / n)
            for key in ("income", "essentials", "unexpected", "everyday", "spending", "to_savings", "net")
        },
        "months_spent_more_than_earned": sum(1 for r in rows if r["net"] < 0),
    }


# ---------------------------------------------------------- safe to spend ---


def _next_day_of_month(after: dt.date, day: int) -> dt.date:
    """The next date strictly after `after` that falls on the given day of month."""
    year, month = after.year, after.month
    for _ in range(3):
        last = calendar.monthrange(year, month)[1]
        candidate = dt.date(year, month, min(day, last))
        if candidate > after:
            return candidate
        month += 1
        if month > 12:
            year, month = year + 1, 1
    raise RuntimeError("could not find next day of month")


def _payday(cid: str, today: dt.date) -> dict | None:
    found = db.rows(
        "SELECT tx_date, amount FROM tx WHERE customer_id = ? AND tx_type = 'salary' AND tx_date <= ? ORDER BY tx_date DESC LIMIT 6",
        [cid, today],
    )
    if not found:
        return None
    days = [r["tx_date"].day for r in found]
    try:
        day = statistics.mode(days)
    except statistics.StatisticsError:
        day = days[0]
    return {
        "day_of_month": day,
        "expected_amount": statistics.median(r["amount"] for r in found),
        "next": _next_day_of_month(today, day),
        "last": found[0]["tx_date"],
    }


COMMITTED_TYPES = {
    "housing_payment": "Housing payment",
    "utilities_payment": "Utility bills",
    "investment_deposit": "Regular investment deposit",
    "salary_sweep": "Regular transfer to another account",
}

DEFAULT_SAVINGS_GOAL_PCT = 10.0
CUSHION_MONTHS = 3


def bill_habits(cid: str, today: dt.date) -> dict[str, dict]:
    """How each kind of bill behaves, read from the last six complete months.

    A bill that comes about once a month (housing, a regular investment deposit, a regular
    transfer) and was paid in at least four of the six months is "monthly": it has a usual day
    and a usual amount (both medians), and it is planned for every month, also after a month in
    which it was missed. Anything else (utilities: several bills a month on changing days) is
    "spread": a monthly average with no dates.
    """
    ref = periods.complete_months(today, 6)
    found = db.rows(
        """
        SELECT tx_type, tx_date, -amount AS amount FROM tx
        WHERE customer_id = ? AND tx_type IN ('housing_payment', 'utilities_payment', 'investment_deposit', 'salary_sweep')
          AND tx_date BETWEEN ? AND ?
        ORDER BY tx_date
        """,
        [cid, ref.start, today],
    )
    habits: dict[str, dict] = {}
    for tx_type in COMMITTED_TYPES:
        mine = [r for r in found if r["tx_type"] == tx_type]
        in_ref = [r for r in mine if r["tx_date"] <= ref.end]
        if not in_ref:
            continue
        months_seen = len({(r["tx_date"].year, r["tx_date"].month) for r in in_ref})
        monthly = len(in_ref) / 6.0 <= 1.5 and months_seen >= 4
        total = sum(r["amount"] for r in in_ref)
        habits[tx_type] = {
            "monthly": monthly,
            "a_month": statistics.median(r["amount"] for r in in_ref) if monthly else total / 6.0,
            "usual_day": int(round(statistics.median(r["tx_date"].day for r in in_ref))) if monthly else None,
            "months_seen": months_seen,
            "paid_months": {(r["tx_date"].year, r["tx_date"].month) for r in mine},
            "a_day": None if monthly else total / ref.days,
        }
    return habits


def expected_bills(cid: str, today: dt.date, start: dt.date, end: dt.date) -> dict:
    """The bills to expect between two dates.

    A monthly bill (see bill_habits) is expected once in every month that has not had one yet,
    on its usual day at its usual amount. If the usual day has passed and it has not been paid,
    it is expected at once. Spread bills cannot be dated, so they come as a daily rate.
    """
    dated: list[dict] = []
    per_day: dict[str, float] = {}
    for tx_type, habit in bill_habits(cid, today).items():
        if not habit["monthly"]:
            per_day[tx_type] = habit["a_day"]
            continue
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            if (year, month) not in habit["paid_months"]:
                due = dt.date(year, month, min(habit["usual_day"], calendar.monthrange(year, month)[1]))
                late = due < start
                if late:
                    due = start
                if due <= end:
                    dated.append({"date": due, "tx_type": tx_type, "what": COMMITTED_TYPES[tx_type], "amount": habit["a_month"], "late": late})
            month += 1
            if month > 12:
                year, month = year + 1, 1
    dated.sort(key=lambda b: b["date"])
    return {"dated": dated, "per_day": per_day, "per_day_total": sum(per_day.values())}


def safe_to_spend(customer_id: str, savings_goal_pct: float = DEFAULT_SAVINGS_GOAL_PCT) -> dict:
    """How much can go to everyday spending before the next payday.

    The pay period is budgeted basket by basket:

        expected salary
        - regular essentials   (bills, plus groceries and transport at your usual pace)
        - unexpected buffer    (your 12-month monthly average, set aside)
        - savings goal         (10% of salary by default, less what you already invest)
        = everyday budget for the pay period
        - everyday spending since payday
        = safe to spend until the next payday

    The result is also capped by what the balance can actually cover once the
    bills due before payday are paid, so it never points into overdraft.
    """
    cid = customer(customer_id)["customer_id"]
    savings_goal_pct = max(0.0, min(float(savings_goal_pct), 60.0))
    today = db.today()
    balance = db.scalar(
        "SELECT arg_max(balance_after, tx_ts) FROM tx WHERE customer_id = ? AND tx_date <= ?", [cid, today]
    ) or 0.0
    avg = db.row("SELECT * FROM cust_avg WHERE customer_id = ?", [cid]) or {}
    payday = _payday(cid, today)

    incoming = 0.0
    if payday and (payday["next"] - today).days <= 1:
        # Payday is tomorrow: plan the pay period that starts then.
        cycle_start = payday["next"]
        next_payday = _next_day_of_month(cycle_start, payday["day_of_month"])
        incoming = payday["expected_amount"]
    elif payday:
        cycle_start = payday["last"]
        next_payday = payday["next"]
    else:
        cycle_start = today.replace(day=1)
        next_payday = _next_day_of_month(today, 1)
    income = payday["expected_amount"] if payday else float(avg.get("income") or 0.0)
    cycle_days = max((next_payday - cycle_start).days, 1)
    window_start = max(today + dt.timedelta(days=1), cycle_start)
    window_end = next_payday - dt.timedelta(days=1)
    days = max((window_end - window_start).days + 1, 1)

    # A monthly bill is budgeted at its usual amount for every month, also after a month in which
    # it was missed; other bills at their six-month average (see bill_habits).
    committed = {tx_type: habit["a_month"] for tx_type, habit in bill_habits(cid, today).items()}
    pace = db.row(
        """
        SELECT
            coalesce(-sum(amount) FILTER (WHERE basket = 'essentials' AND tx_type = 'purchase'), 0) / 90.0 AS essentials_per_day,
            coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) / 90.0 AS everyday_per_day
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
        """,
        [cid, today - dt.timedelta(days=89), today],
    )
    spent = db.scalar(
        "SELECT coalesce(-sum(amount), 0) FROM tx WHERE customer_id = ? AND basket = 'everyday' AND tx_date BETWEEN ? AND ?",
        [cid, cycle_start, today],
    ) if cycle_start <= today else 0.0

    # The pay-period budget, basket by basket.
    budget_lines = [{"label": "Expected salary this pay period", "amount": _r(income), "basket": None}]
    bills_total = 0.0
    for tx_type, label in COMMITTED_TYPES.items():
        if tx_type == "investment_deposit":
            continue
        amount = committed.get(tx_type, 0.0)
        if amount >= 1:
            bills_total += amount
            basket = "essentials" if tx_type in ("housing_payment", "utilities_payment") else None
            budget_lines.append({"label": label, "amount": _r(-amount), "basket": basket})
    essentials_cycle = pace["essentials_per_day"] * cycle_days
    budget_lines.append(
        {"label": "Groceries and transport at your usual pace", "amount": _r(-essentials_cycle), "basket": "essentials"}
    )
    buffer = float(avg.get("unexpected") or 0.0) * cycle_days / 30.4375
    budget_lines.append({"label": "Set aside for unexpected necessities", "amount": _r(-buffer), "basket": "unexpected"})
    goal = income * savings_goal_pct / 100.0
    auto_invest = committed.get("investment_deposit", 0.0)
    saving = max(goal, auto_invest)
    if saving >= 1:
        label = f"Savings goal ({savings_goal_pct:g}% of salary)"
        if auto_invest >= 1:
            label += f", of which EUR {auto_invest:,.0f} is your regular investment deposit"
        budget_lines.append({"label": label, "amount": _r(-saving), "basket": None})
    everyday_budget = income - bills_total - essentials_cycle - buffer - saving
    budget_lines.append({"label": "Everyday budget for this pay period", "amount": _r(everyday_budget), "basket": "everyday", "total": True})
    budget_lines.append({"label": f"Everyday spending since {cycle_start.isoformat()}", "amount": _r(-spent), "basket": "everyday"})
    remaining = everyday_budget - spent
    budget_lines.append({"label": "Left for everyday spending until payday", "amount": _r(remaining), "basket": "everyday", "total": True})

    # What the balance can cover: the bills still expected before payday. A monthly bill that
    # has not been paid yet this month counts in full, on its usual day (see expected_bills).
    coming = expected_bills(cid, today, window_start, window_end)
    due = sum(b["amount"] for b in coming["dated"]) + coming["per_day_total"] * days
    essentials_window = pace["essentials_per_day"] * days
    liquidity = balance + incoming - due - essentials_window

    safe = max(0.0, min(remaining, liquidity))
    limited_by = "balance" if liquidity < remaining else "budget"
    per_day = safe / days
    usual_per_day = pace["everyday_per_day"]
    days_left_this_week = (6 - today.weekday()) or 7
    week_days = min(days_left_this_week, days)

    if liquidity <= 0:
        status = "short"
    elif remaining <= 0:
        status = "over_budget"
    elif usual_per_day <= 0 or per_day >= 1.2 * usual_per_day:
        status = "comfortable"
    elif per_day >= 0.8 * usual_per_day:
        status = "on_track"
    else:
        status = "tight"

    monthly_spend = float(avg.get("spend") or 0.0)
    cushion_months = balance / monthly_spend if monthly_spend > 0 else None
    idle = max(0.0, balance - CUSHION_MONTHS * monthly_spend)
    spare_this_period = max(0.0, safe - usual_per_day * days)
    could_save_now = min(spare_this_period, max(0.0, liquidity)) // 10 * 10

    return {
        "customer_id": cid,
        "as_of": today.isoformat(),
        "pay_period": {
            "from": cycle_start.isoformat(),
            "next_payday": next_payday.isoformat(),
            "payday_in_days": (next_payday - today).days,
            "days_left": days,
            "expected_salary": _r(income),
        },
        "safe_to_spend_until_payday": _r(safe),
        "safe_per_day": _r(per_day),
        "this_week": {
            "days_left": week_days,
            "until": (today + dt.timedelta(days=week_days)).isoformat(),
            "safe_to_spend": _r(per_day * week_days),
            "your_usual_spending": _r(usual_per_day * week_days),
        },
        "usual_everyday_per_day": _r(usual_per_day),
        "status": status,
        "limited_by": limited_by,
        "savings_goal_pct": savings_goal_pct,
        "budget": budget_lines,
        "balance_check": {
            "balance_today": _r(balance),
            "salary_expected_tomorrow": _r(incoming),
            "bills_due_before_payday": _r(due),
            "bills_expected": [
                {"what": b["what"], "date": b["date"].isoformat(), "amount": _r(b["amount"]), "overdue": b["late"]}
                for b in coming["dated"]
            ],
            "groceries_and_transport_before_payday": _r(essentials_window),
            "balance_can_cover": _r(liquidity),
        },
        "other_accounts": other_accounts(cid),
        "safe_to_save": {
            "now": _r(could_save_now),
            "why": "What is left of this pay period's everyday budget if you keep spending at your usual pace.",
            "balance_covers_months_of_spending": _r(cushion_months, 1),
            "idle_above_cushion": _r(idle),
            "cushion_months": CUSHION_MONTHS,
        },
    }


# ------------------------------------------------------------ can I afford ---


def basket_for_purchase(category: str | None, amount: float) -> tuple[str, str]:
    """The basket a new purchase would fall into, with the reason. Mirrors baskets.BASKET_SQL."""
    big = amount >= baskets.BIG_PURCHASE_EUR
    if category in ("Housing", "Utilities", "Groceries"):
        return "essentials", f"{category} is a regular essential."
    if category == "Health":
        return "unexpected", "Health is necessary, but you cannot plan when."
    if category == "Home & Tech":
        if big:
            return "unexpected", f"A Home & Tech purchase of EUR {baskets.BIG_PURCHASE_EUR} or more counts as replacing or repairing something."
        return "everyday", "A smaller Home & Tech purchase is your own choice."
    if category == "Transportation":
        if big:
            return "unexpected", f"A transport payment of EUR {baskets.BIG_PURCHASE_EUR} or more looks like a repair."
        return "essentials", "Getting around is a regular essential."
    return "everyday", "This is your own choice, so it comes out of everyday spending."


def _everyday_fit(amount: float, week: float, until: float, per_day: float) -> dict:
    """An own-choice purchase against what is safe to spend this week and until payday."""
    out: dict = {
        "everyday_budget": {
            "safe_this_week": _r(week),
            "safe_until_payday": _r(until),
            "left_this_week_after": _r(week - amount),
            "left_until_payday_after": _r(until - amount),
            "share_of_safe_until_payday_pct": _pct(amount, until),
            "days_of_everyday_budget": _r(amount / per_day, 1) if per_day > 0 else None,
        }
    }
    if amount <= week:
        out["fits"] = "yes"
        out["why"] = f"It fits within the EUR {week:,.0f} that is safe to spend this week, and leaves EUR {week - amount:,.0f}."
    elif amount <= until:
        out["fits"] = "tight"
        out["why"] = (
            f"It is more than the EUR {week:,.0f} safe for this week, but it fits within the EUR {until:,.0f} "
            f"safe until payday. It would leave EUR {until - amount:,.0f} for everything else until then."
        )
    else:
        out["fits"] = "not_from_this_budget"
        out["why"] = (
            f"It is EUR {amount - until:,.0f} more than what is safe to spend until payday (EUR {until:,.0f}). "
            "The balance covers it, but it would come out of your savings goal or the money for essentials."
        )
    return out


def can_afford(customer_id: str, amount: float, what: str | None = None, category: str | None = None) -> dict:
    """Whether one purchase fits right now, and what it would leave.

    An everyday purchase is checked against what is safe to spend this week
    and until payday. A necessity is checked against what the balance can
    cover, and against the everyday money it would leave until payday.

    A large Home & Tech or transport purchase counts as a necessity by its
    size alone. The bank cannot tell a replaced washing machine from a treat,
    so such a purchase gets both readings: as a necessity, and as a treat.
    """
    cid = customer(customer_id)["customer_id"]
    try:
        amount = float(amount)
    except (TypeError, ValueError) as exc:
        raise EngineError("amount must be a number of euros.") from exc
    if not 0 < amount <= 1_000_000:
        raise EngineError("amount must be a positive number of euros.")
    name = None
    if category:
        name = _match_category(category)
        if not name:
            raise EngineError(f"Unknown category '{category}'. Categories: {', '.join(baskets.SPEND_CATEGORIES)}.")
    basket, reason = basket_for_purchase(name, amount)
    by_size_alone = basket == "unexpected" and name in ("Home & Tech", "Transportation")
    safe = safe_to_spend(cid)
    week = safe["this_week"]["safe_to_spend"]
    until = safe["safe_to_spend_until_payday"]
    per_day = safe["safe_per_day"]
    cover = safe["balance_check"]["balance_can_cover"]
    days_left = safe["pay_period"]["days_left"]
    usual_until = safe["usual_everyday_per_day"] * days_left
    avg = db.row("SELECT unexpected FROM cust_avg WHERE customer_id = ?", [cid]) or {"unexpected": 0.0}
    buffer_month = float(avg["unexpected"] or 0.0)

    result = {
        "customer_id": cid,
        "item": {
            "what": (what or "").strip()[:120] or None,
            "amount": _r(amount),
            "category": name,
            "basket": baskets.BASKETS[basket]["name"],
            "why_this_basket": reason,
        },
        "balance_can_cover_before_payday": _r(cover),
        "balance_left_after": _r(cover - amount),
        "next_payday": safe["pay_period"]["next_payday"],
    }
    if cover < amount:
        result["fits"] = "no"
        result["why"] = (
            f"After the bills due before payday your balance covers EUR {max(cover, 0):,.0f}, "
            f"so this would take the account below zero by EUR {amount - max(cover, 0):,.0f}."
        )
    elif basket == "everyday":
        result.update(_everyday_fit(amount, week, until, per_day))
    else:
        left = cover - amount
        result["unexpected_buffer"] = {
            "set_aside_per_month": _r(buffer_month),
            "months_of_buffer_this_uses": _r(amount / buffer_month, 1) if buffer_month > 0 else None,
        }
        if basket == "unexpected":
            result["until_payday"] = {
                "days": days_left,
                "left_for_everyday_spending_after": _r(left),
                "your_usual_everyday_spending_in_that_time": _r(usual_until),
            }
            if left < usual_until:
                # Paying it is possible, but it eats into the everyday money for the rest of the pay period.
                result["fits"] = "tight"
                result["why"] = (
                    f"A necessity like this is what the unexpected buffer is for, and your balance covers it. "
                    f"But it leaves EUR {left:,.0f} for the {days_left} days until payday, where you usually spend "
                    f"about EUR {usual_until:,.0f} on everyday things. You set aside about EUR {buffer_month:,.0f} "
                    "a month for surprises."
                )
            else:
                result["fits"] = "yes"
                result["why"] = (
                    f"A necessity like this is what the unexpected buffer is for. Your balance covers it and leaves "
                    f"EUR {left:,.0f} before payday. You set aside about EUR {buffer_month:,.0f} a month for surprises."
                )
        else:
            result["fits"] = "yes"
            result["why"] = f"It is a regular essential and your balance covers it, leaving EUR {left:,.0f} before payday."
    if by_size_alone:
        # The size rule cannot tell a replacement from a treat. Give the other reading too.
        result["item"]["basket_depends_on"] = (
            "Whether it replaces or repairs something you need (Unexpected necessities) "
            "or is a treat (Everyday spending). The price alone cannot tell."
        )
        if cover >= amount:
            result["if_it_is_a_treat"] = {
                "basket": baskets.BASKETS["everyday"]["name"],
                **_everyday_fit(amount, week, until, per_day),
            }
    result["safe_to_spend_status"] = safe["status"]
    return result


# ---------------------------------------------------------------- what if ---


def what_if(customer_id: str, target: str, change_pct: float = -20.0, months: int = 12) -> dict:
    """What a change in one kind of spending would do, based on the last 6 months."""
    cid = customer(customer_id)["customer_id"]
    change_pct = float(change_pct)
    if not -100 <= change_pct <= 300:
        raise EngineError("change_pct must be between -100 and 300.")
    months = max(1, min(int(months), 120))
    resolved = resolve_target(target)
    column = resolved["type"]
    marks = ", ".join("?" for _ in resolved["values"])
    ref = periods.complete_months(db.today(), 6)
    found = db.row(
        f"""
        SELECT
            coalesce(-sum(amount) FILTER (WHERE {column} IN ({marks})), 0) / 6.0 AS target_monthly,
            coalesce(count(*) FILTER (WHERE {column} IN ({marks})), 0) / 6.0 AS target_count,
            coalesce(-sum(amount) FILTER (WHERE flow = 'spend'), 0) / 6.0 AS spend_monthly,
            coalesce(sum(amount) FILTER (WHERE flow = 'income'), 0) / 6.0 AS income_monthly
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
        """,
        [*resolved["values"], *resolved["values"], cid, ref.start, ref.end],
    )
    baseline = found["target_monthly"]
    new = baseline * (1 + change_pct / 100.0)
    saving = baseline - new
    net_before = found["income_monthly"] - found["spend_monthly"]
    net_after = net_before + saving
    return {
        "customer_id": cid,
        "target": resolved["label"],
        "target_type": resolved["type"],
        "change_pct": change_pct,
        "based_on": ref.as_dict(),
        "monthly_now": _r(baseline),
        "monthly_after": _r(new),
        "payments_per_month_now": _r(found["target_count"], 1),
        "monthly_saving": _r(saving),
        "yearly_saving": _r(saving * 12),
        "saving_over_horizon": {"months": months, "amount": _r(saving * months)},
        "monthly_left_over_now": _r(net_before),
        "monthly_left_over_after": _r(net_after),
        "savings_rate_now_pct": _pct(net_before, found["income_monthly"]),
        "savings_rate_after_pct": _pct(net_after, found["income_monthly"]),
        "share_of_spending_now_pct": _pct(baseline, found["spend_monthly"]),
    }


# -------------------------------------------------------------- recurring ---


def recurring(customer_id: str) -> dict:
    """Regular income and payments, with the usual day and amount."""
    cid = customer(customer_id)["customer_id"]
    today = db.today()
    ref = periods.complete_months(today, 6)
    found = db.rows(
        """
        WITH monthly AS (
            SELECT tx_type, date_trunc('month', tx_date) AS month, sum(amount) AS amount, count(*) AS n,
                   median(day(tx_date)) AS typical_day
            FROM tx WHERE customer_id = ? AND tx_type <> 'purchase' AND tx_date BETWEEN ? AND ?
            GROUP BY 1, 2
        )
        SELECT tx_type, count(*) AS months_seen, median(amount) AS monthly_amount, avg(n) AS per_month,
               CAST(round(median(typical_day)) AS INTEGER) AS typical_day
        FROM monthly GROUP BY 1 ORDER BY abs(median(amount)) DESC
        """,
        [cid, ref.start, ref.end],
    )
    items = []
    for r in found:
        regular = r["months_seen"] >= 5
        item = {
            "what": baskets.TYPE_LABELS.get(r["tx_type"], r["tx_type"]),
            "direction": "in" if r["monthly_amount"] > 0 else "out",
            "monthly_amount": _r(abs(r["monthly_amount"])),
            "payments_per_month": _r(r["per_month"], 1),
            "months_seen_of_6": r["months_seen"],
            "regular": regular,
        }
        if regular and r["per_month"] < 1.5:
            item["usual_day_of_month"] = r["typical_day"]
            item["next_expected"] = _next_day_of_month(today, r["typical_day"]).isoformat()
        items.append(item)
    return {"customer_id": cid, "based_on": ref.as_dict(), "as_of": today.isoformat(), "items": items}


# ---------------------------------------------------------- other accounts ---


def other_accounts(customer_id: str) -> dict | None:
    """Money that leaves for accounts this bank cannot see (the multi-bank view).

    Under PSD2 a customer can let their bank read their accounts at other
    banks. This reports how much of the picture is missing without that.
    Returns None when the customer keeps everything here.
    """
    cid = customer(customer_id)["customer_id"]
    avg = db.row("SELECT income, transfer_out, to_savings FROM cust_avg WHERE customer_id = ?", [cid])
    if not avg or (avg["transfer_out"] or 0) < 1:
        return None
    return {
        "monthly_transfer_to_other_accounts": _r(avg["transfer_out"]),
        "share_of_income_pct": _pct(avg["transfer_out"], avg["income"]),
        "what_this_means": (
            "This much of your income moves to an account at another bank each month, so spending from there is "
            "invisible here. Connecting that account (open banking, PSD2) would let the baskets, safe-to-spend and "
            "comparisons cover your whole financial picture."
        ),
    }


# ---------------------------------------------------------------- overview ---


def overview(customer_id: str) -> dict:
    """The numbers for the home screen."""
    cust = customer(customer_id)
    cid = cust["customer_id"]
    today = db.today()
    balance = db.scalar(
        "SELECT arg_max(balance_after, tx_ts) FROM tx WHERE customer_id = ? AND tx_date <= ?", [cid, today]
    )
    avg = db.row("SELECT * FROM cust_avg WHERE customer_id = ?", [cid])
    return {
        "other_accounts": other_accounts(cid),
        "customer": {
            "customer_id": cid,
            "age": cust["age"],
            "age_band": cust["age_band"],
            "postal_code": cust["postal_code"],
            "area": cust["area"],
        },
        "today": today.isoformat(),
        "balance": _r(balance),
        "monthly_average_last_12_months": {k: _r(v) for k, v in avg.items() if k != "customer_id"} if avg else None,
        "this_month": basket_summary(cid, "this_month"),
        "safe_to_spend": safe_to_spend(cid),
    }
