"""Who you are as a spender, and how you compare with people like you.

Both use the last 12 complete months and the same deterministic rules for
everyone, so the same data always gives the same answer.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

from . import baskets, db, periods
from .engine import EngineError, _pct, _r, customer, other_accounts, resolve_target, safe_to_spend

# Each type is a plain rule over a customer's own numbers. The first rule
# that matches wins, so the order is the priority.
SPENDER_TYPES = [
    {
        "key": "month_end_stretcher",
        "name": "Month-End Stretcher",
        "summary": "Your money often runs out before the month does.",
        "rule": "15 or more days below zero in a year, or 7 or more months where more went out than came in",
        "test": lambda f: f["overdraft_days"] >= 15 or (f["negative_months"] >= 7 and (f["savings_rate"] or 0) < -0.02),
        "tip": "Start with timing, not cutting: line your bills up right after payday and keep a small buffer for the last week.",
    },
    {
        "key": "essentials_heavy",
        "name": "Essentials-Heavy",
        "summary": "Most of your income is already spoken for before the month starts.",
        "rule": "regular essentials take 68% or more of income",
        "test": lambda f: (f["essentials_of_income"] or 0) >= 0.68,
        "tip": "Small everyday cuts will not move much. The big levers are the essentials themselves: housing, energy contracts, the grocery routine.",
    },
    {
        "key": "steady_builder",
        "name": "Steady Builder",
        "summary": "You keep a good share of what you earn, and you invest it regularly.",
        "rule": "15% or more of income left over, with regular investment deposits",
        "test": lambda f: (f["savings_rate"] or 0) >= 0.15 and f["to_savings"] > 0,
        "tip": "Your habit is the hard part and you already have it. Check the cushion on your everyday account is not bigger than it needs to be.",
    },
    {
        "key": "quiet_saver",
        "name": "Quiet Saver",
        "summary": "You spend clearly less than you earn, but the money mostly sits on your account.",
        "rule": "15% or more of income left over, with no regular investment deposits",
        "test": lambda f: (f["savings_rate"] or 0) >= 0.15,
        "tip": "Decide what the surplus is for. Money with a job (buffer, home, investing) tends to stay saved.",
    },
    {
        "key": "big_ticket_spender",
        "name": "Big-Ticket Spender",
        "summary": "Your everyday spending is driven by a few large purchases, not by small ones.",
        "rule": f"40% or more of everyday spending comes from purchases of EUR {baskets.BIG_PURCHASE_EUR} or more",
        "test": lambda f: (f["big_ticket_share"] or 0) >= 0.40 and (f["everyday_share"] or 0) >= 0.24,
        "tip": "Skipping coffees will not change your picture. Planning the two or three big purchases a year will.",
    },
    {
        "key": "little_and_often",
        "name": "Little-and-Often Spender",
        "summary": "Lots of small purchases that are easy to forget, and they add up.",
        "rule": f"more than one everyday purchase under EUR {baskets.SMALL_PURCHASE_EUR} every week",
        "test": lambda f: f["small_per_week"] >= 1.2,
        "tip": "This is the money that slips through your fingers. A weekly everyday allowance works better here than tracking each purchase.",
    },
    {
        "key": "experience_seeker",
        "name": "Experience Seeker",
        "summary": "A large share of your spending goes to things you choose: eating out, fun, shopping, travel.",
        "rule": "everyday spending is 33% or more of all spending",
        "test": lambda f: (f["everyday_share"] or 0) >= 0.33,
        "tip": "Nothing wrong with that if the essentials and a buffer are covered first. Pick the one category you would miss least.",
    },
    {
        "key": "balanced_navigator",
        "name": "Balanced Navigator",
        "summary": "No single habit dominates: essentials, surprises and everyday spending are in proportion.",
        "rule": "none of the other patterns stands out",
        "test": lambda f: True,
        "tip": "You have room to choose a goal. A fixed monthly saving right after payday is the easiest next step.",
    },
]

PEER_GROUPS = {
    "age": ("age_band = ?", lambda c: [c["age_band"]], lambda c: f"customers aged {c['age_band']}"),
    "area": ("area = ?", lambda c: [c["area"]], lambda c: f"customers in {c['area']}"),
    "age_and_area": (
        "age_band = ? AND area = ?",
        lambda c: [c["age_band"], c["area"]],
        lambda c: f"customers aged {c['age_band']} in {c['area']}",
    ),
    "all": ("TRUE", lambda c: [], lambda c: "all customers"),
}

# Metrics that exist as columns of cust_features: name -> (label, unit, kind)
FEATURE_METRICS = {
    "income": ("Monthly income", "eur"),
    "spending": ("Monthly spending", "eur"),
    "savings_rate": ("Share of income left over", "pct"),
    "everyday_share": ("Everyday share of spending", "pct"),
    "essentials_of_income": ("Essentials as share of income", "pct"),
    "small_purchases_per_week": (f"Everyday purchases under EUR {baskets.SMALL_PURCHASE_EUR} per week", "count"),
}
FEATURE_COLUMNS = {"spending": "spend", "small_purchases_per_week": "small_per_week"}


def _features(cid: str) -> dict:
    found = db.row("SELECT * FROM cust_features WHERE customer_id = ?", [cid])
    if not found:
        raise EngineError("Not enough history for this customer.")
    return found


def _peer(cust: dict, peer_group: str) -> tuple[str, list, str]:
    key = (peer_group or "age").strip().lower().replace(" ", "_")
    if key not in PEER_GROUPS:
        raise EngineError(f"peer_group must be one of: {', '.join(PEER_GROUPS)}.")
    cond, params, label = PEER_GROUPS[key]
    return cond, params(cust), label(cust)


def _rank_feature(column: str, value, cond: str, params: list) -> dict:
    found = db.row(
        f"""
        SELECT count(*) AS peers, median({column}) AS median,
               quantile_cont({column}, 0.25) AS p25, quantile_cont({column}, 0.75) AS p75,
               avg(CASE WHEN {column} < ? THEN 1.0 ELSE 0.0 END) AS below
        FROM cust_features JOIN customers USING (customer_id)
        WHERE {cond} AND {column} IS NOT NULL
        """,
        [value, *params],
    )
    return found


def spender_profile(customer_id: str) -> dict:
    """What kind of spender the customer is, with the numbers behind it."""
    cust = customer(customer_id)
    cid = cust["customer_id"]
    f = _features(cid)
    kind = next(t for t in SPENDER_TYPES if t["test"](f))
    cond, params, peer_label = _peer(cust, "age")

    def vs_peers(column: str, value) -> dict:
        r = _rank_feature(column, value, cond, params)
        return {"peer_median": r["median"], "higher_than_pct_of_peers": _r(100 * r["below"], 0)}

    top = db.rows(
        """
        SELECT category, -sum(amount) / 12.0 AS monthly
        FROM tx WHERE customer_id = ? AND basket = 'everyday' AND tx_date BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 2 DESC LIMIT 3
        """,
        [cid, *_window()],
    )
    spend = f["spend"] or 0.0
    everyday = vs_peers("everyday_share", f["everyday_share"])
    saving = vs_peers("savings_rate", f["savings_rate"])
    small = vs_peers("small_per_week", f["small_per_week"])
    return {
        "customer_id": cid,
        "based_on": periods.complete_months(db.today(), 12).as_dict(),
        "spender_type": kind["name"],
        "summary": kind["summary"],
        "why": kind["rule"],
        "tip": kind["tip"],
        "monthly": {
            "income": _r(f["income"]),
            "spending": _r(spend),
            "regular_essentials": _r(f["essentials"]),
            "unexpected_necessities": _r(f["unexpected"]),
            "everyday_spending": _r(f["everyday"]),
            "invested": _r(f["to_savings"]),
            "transferred_to_other_accounts": _r(f["transfer_out"]),
            "left_over": _r(f["income"] - spend - f["transfer_out"]),
        },
        "basket_shares_pct": {
            "regular_essentials": _pct(f["essentials"], spend),
            "unexpected_necessities": _pct(f["unexpected"], spend),
            "everyday_spending": _pct(f["everyday"], spend),
        },
        "traits": {
            "share_of_income_left_over_pct": _r(100 * (f["savings_rate"] or 0), 1),
            "essentials_share_of_income_pct": _r(100 * (f["essentials_of_income"] or 0), 1),
            "small_everyday_purchases_per_week": _r(f["small_per_week"], 1),
            "small_everyday_purchases_monthly_total": _r(f["small_monthly"]),
            "big_purchases_share_of_everyday_pct": _r(100 * (f["big_ticket_share"] or 0), 1),
            "weekend_share_of_everyday_pct": _r(100 * (f["weekend_share"] or 0), 1),
            "restaurants_share_of_everyday_pct": _r(100 * (f["restaurants_share"] or 0), 1),
            "days_below_zero_balance": f["overdraft_days"],
            "months_spent_more_than_earned": f["negative_months"],
            "invests_regularly": f["to_savings"] > 0,
        },
        "top_everyday_categories": [{"category": r["category"], "monthly": _r(r["monthly"])} for r in top],
        "other_accounts": other_accounts(cid),
        "compared_with": peer_label,
        "vs_peers": {
            "everyday_share_of_spending": {
                "you_pct": _r(100 * (f["everyday_share"] or 0), 1),
                "peer_median_pct": _r(100 * (everyday["peer_median"] or 0), 1),
                "higher_than_pct_of_peers": everyday["higher_than_pct_of_peers"],
            },
            "share_of_income_left_over": {
                "you_pct": _r(100 * (f["savings_rate"] or 0), 1),
                "peer_median_pct": _r(100 * (saving["peer_median"] or 0), 1),
                "higher_than_pct_of_peers": saving["higher_than_pct_of_peers"],
            },
            "small_purchases_per_week": {
                "you": _r(f["small_per_week"], 1),
                "peer_median": _r(small["peer_median"], 1),
                "higher_than_pct_of_peers": small["higher_than_pct_of_peers"],
            },
        },
    }


def _window() -> tuple:
    p = periods.complete_months(db.today(), 12)
    return p.start, p.end


def benchmark(customer_id: str, target: str | None = None, peer_group: str = "age") -> dict:
    """Compare the customer's monthly average with their peers.

    target: a basket, a category, a subcategory, or one of the metric names
    (income, spending, savings_rate, everyday_share, ...). Leave empty for an
    overview of the three baskets.
    """
    cust = customer(customer_id)
    cid = cust["customer_id"]
    cond, params, peer_label = _peer(cust, peer_group)
    base = {
        "customer_id": cid,
        "compared_with": peer_label,
        "based_on": periods.complete_months(db.today(), 12).as_dict(),
        "source": "Money Mentor's own customer base (the synthetic S-Bank dataset), monthly averages over 12 months",
    }
    f = _features(cid)

    def feature_item(name: str) -> dict:
        label, unit = FEATURE_METRICS[name]
        column = FEATURE_COLUMNS.get(name, name)
        value = f[column]
        r = _rank_feature(column, value, cond, params)
        scale = 100.0 if unit == "pct" else 1.0
        return {
            "metric": label,
            "unit": unit,
            "you": _r((value or 0) * scale, 1 if unit != "eur" else 2),
            "peer_median": _r((r["median"] or 0) * scale, 1 if unit != "eur" else 2),
            "peer_middle_half": [_r((r["p25"] or 0) * scale, 1), _r((r["p75"] or 0) * scale, 1)],
            "higher_than_pct_of_peers": _r(100 * r["below"], 0),
            "peers": r["peers"],
        }

    def spend_item(resolved: dict) -> dict:
        column = resolved["type"]
        marks = ", ".join("?" for _ in resolved["values"])
        start, end = _window()
        found = db.row(
            f"""
            WITH per AS (
                SELECT c.customer_id, coalesce(-sum(m.amount), 0) / 12.0 AS monthly
                FROM customers c
                LEFT JOIN cust_month m ON m.customer_id = c.customer_id
                    AND m.flow = 'spend' AND m.{column} IN ({marks}) AND m.month BETWEEN ? AND ?
                WHERE {cond}
                GROUP BY 1
            ),
            me AS (
                SELECT coalesce(-sum(amount), 0) / 12.0 AS monthly FROM cust_month
                WHERE customer_id = ? AND flow = 'spend' AND {column} IN ({marks}) AND month BETWEEN ? AND ?
            )
            SELECT (SELECT monthly FROM me) AS you, count(*) AS peers, median(monthly) AS median,
                   quantile_cont(monthly, 0.25) AS p25, quantile_cont(monthly, 0.75) AS p75,
                   avg(CASE WHEN monthly < (SELECT monthly FROM me) THEN 1.0 ELSE 0.0 END) AS below
            FROM per
            """,
            [*resolved["values"], start, end, *params, cid, *resolved["values"], start, end],
        )
        return {
            "metric": f"Monthly spending on {resolved['label']}",
            "unit": "eur",
            "you": _r(found["you"]),
            "peer_median": _r(found["median"]),
            "peer_middle_half": [_r(found["p25"]), _r(found["p75"])],
            "difference_to_median": _r(found["you"] - found["median"]),
            "higher_than_pct_of_peers": _r(100 * found["below"], 0),
            "peers": found["peers"],
        }

    if not target:
        items = [spend_item(resolve_target(b)) for b in baskets.BASKET_ORDER]
        items += [feature_item("income"), feature_item("savings_rate")]
        return {**base, "comparisons": items}

    key = target.strip().lower().replace(" ", "_")
    if key in FEATURE_METRICS:
        return {**base, "comparisons": [feature_item(key)]}
    return {**base, "comparisons": [spend_item(resolve_target(target))]}


# ----------------------------------------------------------------- notices ---


def notices(customer_id: str, limit: int = 4) -> dict:
    """What stands out in the customer's money right now.

    Fixed rules, most urgent first. Each notice carries its numbers, the basket
    it belongs to, and a question the customer can tap to ask about it.
    """
    cust = customer(customer_id)
    cid = cust["customer_id"]
    today = db.today()
    month = periods.complete_months(today, 1)
    before = periods.Period(db.add_months(month.start, -3), month.start - dt.timedelta(days=1), "the three months before")
    safe = safe_to_spend(cid)
    f = _features(cid)
    found: list[dict] = []

    def add(kind: str, title: str, detail: str, ask: str, basket: str | None = None, tone: str = "neutral") -> None:
        found.append({"kind": kind, "title": title, "detail": detail, "ask": ask, "basket": basket, "tone": tone})

    check = safe["balance_check"]
    if safe["status"] == "short":
        add(
            "short_before_payday",
            "Your balance may not last until payday",
            f"After the bills that usually fall due before {safe['pay_period']['next_payday']}, the balance covers "
            f"EUR {check['balance_can_cover']:,.0f}.",
            "What is safe for me to spend until payday?",
            tone="warning",
        )
    elif safe["status"] == "over_budget":
        over = -next(line["amount"] for line in reversed(safe["budget"]) if line.get("total"))
        add(
            "over_everyday_budget",
            f"EUR {over:,.0f} over this pay period's everyday budget",
            "Your everyday spending since payday is already more than the budget that keeps your savings goal.",
            "Where did my everyday spending go this month?",
            basket="everyday",
            tone="warning",
        )

    changes = db.rows(
        """
        SELECT category, any_value(basket) AS basket,
               coalesce(-sum(amount) FILTER (WHERE tx_date BETWEEN ? AND ?), 0) AS now,
               coalesce(-sum(amount) FILTER (WHERE tx_date BETWEEN ? AND ?), 0) / 3.0 AS usual
        FROM tx
        WHERE customer_id = ? AND flow = 'spend' AND tx_type = 'purchase' AND tx_date BETWEEN ? AND ?
        GROUP BY 1
        """,
        [month.start, month.end, before.start, before.end, cid, before.start, month.end],
    )
    ups = sorted((c for c in changes if c["now"] - c["usual"] >= 50 and c["now"] >= 1.25 * c["usual"]), key=lambda c: c["usual"] - c["now"])
    downs = sorted((c for c in changes if c["usual"] - c["now"] >= 50 and c["now"] <= 0.75 * c["usual"]), key=lambda c: c["now"] - c["usual"])
    if ups:
        c = ups[0]
        add(
            "category_up",
            f"{c['category']} was EUR {c['now'] - c['usual']:,.0f} above your usual in {month.label}",
            f"EUR {c['now']:,.0f} against a usual EUR {c['usual']:,.0f} a month.",
            f"Why was my {c['category'].lower()} spending higher in {month.label}?",
            basket=c["basket"],
        )

    surprise = db.row(
        """
        SELECT tx_date, subcategory, -amount AS amount FROM tx
        WHERE customer_id = ? AND basket = 'unexpected' AND -amount >= ? AND tx_date BETWEEN ? AND ?
        ORDER BY -amount DESC LIMIT 1
        """,
        [cid, baskets.BIG_PURCHASE_EUR, today - dt.timedelta(days=29), today],
    )
    if surprise:
        add(
            "unexpected_hit",
            f"An unexpected EUR {surprise['amount']:,.0f} for {surprise['subcategory'].lower()}",
            f"On {surprise['tx_date'].isoformat()}. This is what the buffer is for: you set aside about "
            f"EUR {f['unexpected']:,.0f} a month on average for things like this.",
            "How much do unexpected necessities cost me in a year?",
            basket="unexpected",
        )

    if (f["small_monthly"] or 0) >= 40:
        add(
            "small_purchases",
            f"Small purchases add up to EUR {f['small_monthly']:,.0f} a month",
            f"About {f['small_per_week']:.1f} everyday purchases under EUR {baskets.SMALL_PURCHASE_EUR} a week. "
            "Easy to forget, so they are worth seeing in one number.",
            "Show me my small everyday purchases",
            basket="everyday",
        )

    idle = safe["safe_to_save"]["idle_above_cushion"]
    if idle >= 1000:
        add(
            "idle_cash",
            f"EUR {idle:,.0f} sits beyond a {safe['safe_to_save']['cushion_months']}-month cushion",
            f"Your balance covers {safe['safe_to_save']['balance_covers_months_of_spending']:g} months of spending. "
            "Money above a cushion could have a job: a goal, or long-term saving.",
            "How much is safe for me to save?",
            tone="positive",
        )

    if f["overdraft_days"] >= 5:
        add(
            "days_below_zero",
            f"{f['overdraft_days']} days below zero in the last year",
            "Lining bills up right after payday, or a small buffer, usually fixes this faster than cutting spending.",
            "When does my balance usually run low?",
            tone="warning",
        )

    if downs:
        c = downs[0]
        add(
            "category_down",
            f"EUR {c['usual'] - c['now']:,.0f} less on {c['category'].lower()} than usual",
            f"EUR {c['now']:,.0f} in {month.label} against a usual EUR {c['usual']:,.0f}.",
            f"What would I save in a year if I kept {c['category'].lower()} at this level?",
            basket=c["basket"],
            tone="positive",
        )

    other = other_accounts(cid)
    if other:
        add(
            "other_bank",
            f"{other['share_of_income_pct']:g}% of your income moves to another bank",
            "Spending from that account is invisible here. Connecting it would complete the picture.",
            "What can you not see about my money?",
        )

    return {"customer_id": cid, "as_of": today.isoformat(), "month": month.as_dict(), "notices": found[: max(1, int(limit))]}


# ---------------------------------------------------------------- personas ---

# Demo identities. The data is synthetic and has no names, so these labels
# are ours: each picks one real customer_id by a rule, so the demo always
# shows the same people.
_PERSONA_RULES = [
    (
        "First-job starter",
        "Under 25, modest income, lots of small purchases",
        "SELECT f.customer_id FROM cust_features f JOIN customers c USING (customer_id) "
        "WHERE c.age BETWEEN 20 AND 24 AND f.small_per_week >= 1.5 AND f.transfer_out = 0 "
        "AND f.savings_rate BETWEEN 0 AND 0.12 AND f.overdraft_days < 10 ORDER BY f.small_per_week DESC, f.customer_id LIMIT 1",
    ),
    (
        "Month-end stretcher",
        "Balance dips below zero most months",
        "SELECT f.customer_id FROM cust_features f JOIN customers c USING (customer_id) "
        "WHERE f.overdraft_days BETWEEN 30 AND 70 AND c.age BETWEEN 28 AND 45 AND f.transfer_out = 0 ORDER BY f.overdraft_days DESC, f.customer_id LIMIT 1",
    ),
    (
        "Home buyer, approved",
        "Applied for a mortgage and got it",
        "SELECT m.customer_id FROM mtg_final m JOIN cust_features f USING (customer_id) "
        "WHERE m.final_decision = 'approved' AND f.transfer_out = 0 AND f.savings_rate > 0.05 ORDER BY abs(m.property_price - 260000), m.customer_id LIMIT 1",
    ),
    (
        "Home buyer, turned down",
        "Mortgage rejected for too little equity",
        "SELECT m.customer_id FROM mtg_final m JOIN cust_features f USING (customer_id) "
        "WHERE m.rejection_reason = 'insufficient_equity' ORDER BY f.transfer_out, m.customer_id LIMIT 1",
    ),
    (
        "Steady builder",
        "Saves and invests every month",
        "SELECT f.customer_id FROM cust_features f JOIN customers c USING (customer_id) "
        "WHERE f.savings_rate BETWEEN 0.18 AND 0.30 AND f.to_savings > 150 AND f.transfer_out = 0 AND c.age BETWEEN 30 AND 50 "
        "AND f.overdraft_days = 0 ORDER BY f.to_savings DESC, f.customer_id LIMIT 1",
    ),
    (
        "Experience seeker",
        "A third of spending goes to eating out, fun and travel",
        "SELECT f.customer_id FROM cust_features f JOIN customers c USING (customer_id) "
        "WHERE f.everyday_share BETWEEN 0.38 AND 0.50 AND f.transfer_out = 0 AND f.overdraft_days < 5 AND c.age BETWEEN 25 AND 40 "
        "AND f.big_ticket_share < 0.35 ORDER BY f.restaurants_share DESC, f.customer_id LIMIT 1",
    ),
    (
        "Two-bank customer",
        "Moves most of the salary to another bank each month",
        "SELECT f.customer_id FROM cust_features f WHERE f.transfer_out > 1000 ORDER BY f.customer_id LIMIT 1",
    ),
    (
        "Pensioner",
        "Over 65 with a steady, essentials-first budget",
        "SELECT f.customer_id FROM cust_features f JOIN customers c USING (customer_id) "
        "WHERE c.age >= 68 AND f.transfer_out = 0 AND f.overdraft_days = 0 ORDER BY abs(f.income - 2400), f.customer_id LIMIT 1",
    ),
]


@lru_cache(maxsize=1)
def personas() -> list[dict]:
    """A fixed set of demo customers, each chosen by a rule."""
    out = []
    seen = set()
    for label, blurb, sql in _PERSONA_RULES:
        cid = db.scalar(sql)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        cust = customer(cid)
        f = _features(cid)
        out.append(
            {
                "customer_id": cid,
                "label": label,
                "blurb": blurb,
                "age": cust["age"],
                "area": cust["area"],
                "monthly_income": _r(f["income"], 0),
            }
        )
    return out
