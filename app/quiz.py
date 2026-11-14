"""The basket quiz: sort six of your own payments into the three baskets.

S-Bank's teaching idea is easier to remember after doing it once with your
own money. The quiz picks real payments from the customer's last six months,
mixing easy ones (rent) with the ones people get wrong (a taxi is everyday
spending although other transport is an essential; a EUR 400 home purchase is
an unexpected necessity although a EUR 40 one is everyday spending).

The answers come from the same rules that sort every payment (baskets.py).
"""

from __future__ import annotations

import hashlib

from . import baskets, db, periods
from .engine import _pct, _r, customer

BIG = baskets.BIG_PURCHASE_EUR

# (kind, SQL condition, why this is in its basket). Ordered so that the
# trickiest kinds are tried first for each basket.
KINDS = [
    ("taxi", "mcc = '4121'", "A taxi is your own choice, so it is everyday spending, even though other transport is an essential."),
    ("home_small", f"category = 'Home & Tech' AND -amount < {BIG}", "A smaller Home & Tech purchase is your own choice: everyday spending."),
    ("eating_out", "category = 'Restaurants'", "Eating out is your own choice: everyday spending."),
    ("fun", "category IN ('Entertainment', 'Lifestyle', 'Travel')", "This is your own choice, the kind of money that slips through your fingers: everyday spending."),
    ("home_big", f"category = 'Home & Tech' AND -amount >= {BIG}", f"A Home & Tech purchase of EUR {BIG} or more counts as replacing or repairing something: an unexpected necessity."),
    ("health", "category = 'Health'", "Health costs are necessary, but you cannot plan when they come: an unexpected necessity."),
    ("transport_big", f"category = 'Transportation' AND mcc IS DISTINCT FROM '4121' AND -amount >= {BIG}", f"A transport payment of EUR {BIG} or more looks like a repair: an unexpected necessity."),
    ("housing", "tx_type = 'housing_payment'", "Housing is a regular essential: you have to pay it, and you know when."),
    ("bills", "tx_type = 'utilities_payment'", "Utility bills are a regular essential: you have to pay them, and they come every month."),
    ("groceries", "category = 'Groceries'", "Groceries are a regular essential."),
    ("transport", f"category = 'Transportation' AND mcc IS DISTINCT FROM '4121' AND -amount < {BIG}", "Getting around (public transport, fuel, parking) is a regular essential."),
]

PER_BASKET = 2


def basket_quiz(customer_id: str) -> dict:
    """Six of the customer's own recent payments, with the basket each belongs to and why."""
    cid = customer(customer_id)["customer_id"]
    period = periods.complete_months(db.today(), 6)
    picked: dict[str, list[dict]] = {b: [] for b in baskets.BASKET_ORDER}
    for kind, condition, why in KINDS:
        found = db.row(
            f"""
            SELECT tx_date, subcategory, category, -amount AS amount, basket
            FROM tx
            WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ? AND {condition}
            ORDER BY tx_date DESC, -amount DESC LIMIT 1
            """,
            [cid, period.start, period.end],
        )
        if not found or len(picked[found["basket"]]) >= PER_BASKET:
            continue
        picked[found["basket"]].append(
            {
                "kind": kind,
                "date": found["tx_date"].isoformat(),
                "what": found["subcategory"],
                "category": found["category"],
                "amount": _r(found["amount"]),
                "basket": found["basket"],
                "why": why,
            }
        )
    items = [item for basket in baskets.BASKET_ORDER for item in picked[basket]]
    # A fixed shuffle per customer: the same person always gets the same order.
    items.sort(key=lambda item: hashlib.sha256(f"{cid}:{item['kind']}".encode()).hexdigest())

    split = db.row(
        """
        SELECT
            coalesce(-sum(amount) FILTER (WHERE basket = 'essentials'), 0) AS essentials,
            coalesce(-sum(amount) FILTER (WHERE basket = 'unexpected'), 0) AS unexpected,
            coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) AS everyday
        FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN ? AND ?
        """,
        [cid, period.start, period.end],
    )
    total = sum(split.values())
    return {
        "customer_id": cid,
        "period": period.as_dict(),
        "baskets": [
            {"basket": key, "name": baskets.BASKETS[key]["name"], "emoji": baskets.BASKETS[key]["emoji"], "meaning": baskets.BASKETS[key]["meaning"]}
            for key in baskets.BASKET_ORDER
        ],
        "questions": items,
        "your_real_split": [
            {"basket": key, "name": baskets.BASKETS[key]["name"], "total": _r(split[key]), "share_pct": _pct(split[key], total) or 0.0}
            for key in baskets.BASKET_ORDER
        ],
    }
