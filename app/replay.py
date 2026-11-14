"""Your year, replayed.

Take the customer's real transactions for the last 12 months, change one
habit, and replay the account balance day by day. The result is not a
forecast and not a model: it is their own history with one rule applied.

Each rule ("lever") says how much less a given payment would have been. The
levers are ranked by what they would have left on the account, so the advice
a customer sees is the one that mattered most in their own year.

Two honest limits, which the result states:
- It is arithmetic. It assumes money not spent stayed on the account.
- A lever that mattered last year may not matter next year. So each lever is
  also replayed on the year before, to show whether the pattern holds.
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from typing import Callable

from . import baskets, db, periods
from .engine import EngineError, _pct, _r, customer

SMALL = baskets.SMALL_PURCHASE_EUR
BIG = baskets.BIG_PURCHASE_EUR

LEVERS = ["weekly_rhythm", "everyday_less", "small_purchases", "big_purchases", "top_category"]

LEVER_TEXT = {
    "weekly_rhythm": {
        "title": "Trim your heaviest weeks to a normal busy week",
        "how": "Only the heaviest quarter of your weeks is trimmed, down to the level of an ordinary busy week for you. Every other week stays as it was.",
    },
    "everyday_less": {
        "title": "Spend 20% less on everyday things",
        "how": "The same 20% off every everyday purchase.",
    },
    "small_purchases": {
        "title": f"Halve the purchases under EUR {SMALL}",
        "how": f"Every second everyday purchase under EUR {SMALL} is skipped: the ones that slip through your fingers.",
    },
    "big_purchases": {
        "title": f"Halve the everyday purchases of EUR {BIG} or more",
        "how": f"Each everyday purchase of EUR {BIG} or more costs half: a cheaper choice, or every second one skipped.",
    },
    "top_category": {
        "title": "Spend 30% less on your biggest everyday category",
        "how": "30% off every purchase in the everyday category you spend most on.",
    },
}


def _monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def _load(cid: str, start: dt.date, end: dt.date) -> list[dict]:
    return db.rows(
        """
        SELECT tx_date, amount, balance_after, basket, category
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ? ORDER BY tx_ts
        """,
        [cid, start, end],
    )


def _context(rows: list[dict], start: dt.date, end: dt.date) -> dict:
    """What the rules need to know about the year: weekly totals, the usual week, the top category."""
    weekly: dict[dt.date, float] = defaultdict(float)
    by_category: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["basket"] == "everyday":
            weekly[_monday(r["tx_date"])] += -r["amount"]
            by_category[r["category"]] += -r["amount"]
    weeks = sorted({_monday(start + dt.timedelta(days=i)) for i in range((end - start).days + 1)})
    totals = [weekly.get(w, 0.0) for w in weeks]
    usual_week = statistics.median(totals) if totals else 0.0
    # A "normal busy week": three weeks in four were at or below this.
    busy_week = statistics.quantiles(totals, n=4, method="inclusive")[2] if len(totals) >= 4 else usual_week
    top_category = max(by_category, key=by_category.get) if by_category else None
    return {"weekly": weekly, "weeks": weeks, "usual_week": usual_week, "busy_week": busy_week, "top_category": top_category}


def _rule(lever: str, ctx: dict) -> Callable[[dict], float]:
    """How many euros less this payment would have been under the lever."""
    weekly, cap = ctx["weekly"], ctx["busy_week"]
    top = ctx["top_category"]

    def everyday(r: dict) -> bool:
        return r["basket"] == "everyday"

    if lever == "weekly_rhythm":
        def kept(r: dict) -> float:
            if not everyday(r) or cap <= 0:
                return 0.0
            total = weekly[_monday(r["tx_date"])]
            return -r["amount"] * (1 - cap / total) if total > cap else 0.0
    elif lever == "everyday_less":
        def kept(r: dict) -> float:
            return 0.2 * -r["amount"] if everyday(r) else 0.0
    elif lever == "small_purchases":
        def kept(r: dict) -> float:
            return 0.5 * -r["amount"] if everyday(r) and -r["amount"] < SMALL else 0.0
    elif lever == "big_purchases":
        def kept(r: dict) -> float:
            return 0.5 * -r["amount"] if everyday(r) and -r["amount"] >= BIG else 0.0
    elif lever == "top_category":
        def kept(r: dict) -> float:
            return 0.3 * -r["amount"] if everyday(r) and top and r["category"] == top else 0.0
    else:
        raise EngineError(f"Unknown lever '{lever}'. Levers: {', '.join(LEVERS)}.")
    return kept


def _run(rows: list[dict], rule: Callable[[dict], float]) -> dict:
    kept = 0.0
    below_before: set[dt.date] = set()
    below_after: set[dt.date] = set()
    low_before = low_after = None
    low_by_week: dict[dt.date, float] = {}
    for r in rows:
        kept += rule(r)
        before = r["balance_after"]
        after = before + kept
        if before < 0:
            below_before.add(r["tx_date"])
        if after < 0:
            below_after.add(r["tx_date"])
        low_before = before if low_before is None else min(low_before, before)
        low_after = after if low_after is None else min(low_after, after)
        week = _monday(r["tx_date"])
        low_by_week[week] = min(low_by_week.get(week, after), after)
    end_before = rows[-1]["balance_after"] if rows else 0.0
    return {
        "kept": kept,
        "days_below_zero_before": len(below_before),
        "days_below_zero_after": len(below_after),
        "lowest_before": low_before or 0.0,
        "lowest_after": low_after or 0.0,
        "end_before": end_before,
        "end_after": end_before + kept,
        "low_by_week": low_by_week,
    }


def _rank(rows: list[dict], ctx: dict) -> list[tuple[str, dict]]:
    results = [(lever, _run(rows, _rule(lever, ctx))) for lever in LEVERS]
    # Most money kept first; fewer days below zero breaks a tie.
    results.sort(key=lambda item: (-item[1]["kept"], item[1]["days_below_zero_after"]))
    return results


def _title(lever: str, ctx: dict) -> str:
    title = LEVER_TEXT[lever]["title"]
    if lever == "weekly_rhythm":
        return f"{title} (EUR {ctx['busy_week']:,.0f})"
    if lever == "top_category" and ctx["top_category"]:
        return f"Spend 30% less on {ctx['top_category']}, your biggest everyday category"
    return title


def check_in(customer_id: str, weekly_ceiling: float) -> dict:
    """How the last four full weeks, and this week so far, compare with a weekly everyday ceiling."""
    cid = customer(customer_id)["customer_id"]
    today = db.today()
    this_monday = _monday(today)
    first = this_monday - dt.timedelta(weeks=4)
    spent = {
        r["week"]: r["total"]
        for r in db.rows(
            """
            SELECT CAST(date_trunc('week', tx_date) AS DATE) AS week, -sum(amount) AS total
            FROM tx WHERE customer_id = ? AND basket = 'everyday' AND tx_date BETWEEN ? AND ?
            GROUP BY 1
            """,
            [cid, first, today],
        )
    }
    weeks = []
    for i in range(4):
        start = first + dt.timedelta(weeks=i)
        total = float(spent.get(start, 0.0))
        weeks.append(
            {
                "week_start": start.isoformat(),
                "week_end": (start + dt.timedelta(days=6)).isoformat(),
                "everyday_spending": _r(total),
                "within_ceiling": total <= weekly_ceiling,
                "over_by": _r(max(0.0, total - weekly_ceiling)),
            }
        )
    so_far = float(spent.get(this_monday, 0.0))
    return {
        "weekly_ceiling": _r(weekly_ceiling),
        "last_four_weeks": weeks,
        "weeks_within_ceiling": sum(1 for w in weeks if w["within_ceiling"]),
        "this_week": {
            "week_start": this_monday.isoformat(),
            "spent_so_far": _r(so_far),
            "left": _r(max(0.0, weekly_ceiling - so_far)),
            "days_left": 6 - today.weekday(),
        },
    }


def replay(customer_id: str, lever: str | None = None) -> dict:
    """Replay the last 12 months with one habit changed, and rank the levers.

    lever: one of weekly_rhythm, everyday_less, small_purchases, big_purchases,
    top_category. Left empty, the lever that would have kept the most is shown.
    """
    cid = customer(customer_id)["customer_id"]
    if lever is not None:
        lever = str(lever).strip().lower().replace(" ", "_").replace("-", "_")
        if lever not in LEVERS:
            raise EngineError(f"Unknown lever '{lever}'. Levers: {', '.join(LEVERS)}.")

    year = periods.complete_months(db.today(), 12)
    rows = _load(cid, year.start, year.end)
    if not rows:
        raise EngineError("There are no transactions in the last 12 months to replay.")
    ctx = _context(rows, year.start, year.end)
    ranked = _rank(rows, ctx)
    actual = _run(rows, lambda r: 0.0)

    # The same levers on the year before: does the pattern hold?
    prev_start = db.add_months(year.start, -12)
    prev_end = year.start - dt.timedelta(days=1)
    prev_rows = _load(cid, prev_start, prev_end)
    prev_ranked = _rank(prev_rows, _context(prev_rows, prev_start, prev_end)) if len(prev_rows) >= 50 else []
    prev_order = [name for name, _ in prev_ranked]
    prev_kept = {name: res["kept"] for name, res in prev_ranked}

    income = db.scalar(
        "SELECT coalesce(sum(amount), 0) FROM tx WHERE customer_id = ? AND flow = 'income' AND tx_date BETWEEN ? AND ?",
        [cid, year.start, year.end],
    ) or 0.0

    def lever_entry(position: int, name: str, res: dict) -> dict:
        entry = {
            "rank": position,
            "lever": name,
            "title": _title(name, ctx),
            "how": LEVER_TEXT[name]["how"],
            "kept_over_the_year": _r(res["kept"]),
            "kept_per_month": _r(res["kept"] / 12.0),
            "share_of_income_pct": _pct(res["kept"], income),
            "days_below_zero": {"before": res["days_below_zero_before"], "after": res["days_below_zero_after"]},
            "lowest_balance": {"before": _r(res["lowest_before"]), "after": _r(res["lowest_after"])},
            "balance_today": {"before": _r(res["end_before"]), "after": _r(res["end_after"])},
        }
        if prev_ranked:
            entry["year_before"] = {
                "kept": _r(prev_kept[name]),
                "rank": prev_order.index(name) + 1,
            }
        return entry

    levers = [lever_entry(i + 1, name, res) for i, (name, res) in enumerate(ranked)]
    worthwhile = [entry for entry in levers if entry["kept_over_the_year"] >= 1]
    chosen_name = lever or (worthwhile[0]["lever"] if worthwhile else ranked[0][0])
    chosen = next(res for name, res in ranked if name == chosen_name)
    chosen_entry = next(entry for entry in levers if entry["lever"] == chosen_name)

    weeks = ctx["weeks"]

    def weekly_series(low_by_week: dict[dt.date, float]) -> list[int]:
        out, last = [], rows[0]["balance_after"]
        for week in weeks:
            last = low_by_week.get(week, last)
            out.append(round(last))
        return out

    honesty = None
    if prev_ranked:
        same_top = bool(worthwhile) and prev_order[0] == worthwhile[0]["lever"]
        honesty = {
            "year_before": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
            "top_lever_was_also_top_the_year_before": same_top,
            "this_lever_rank_the_year_before": prev_order.index(chosen_name) + 1,
            "this_lever_kept_the_year_before": _r(prev_kept[chosen_name]),
            "note": (
                "Your biggest lever was the same in both years, so it is a habit, not a one-off."
                if same_top
                else "Your biggest lever was a different one the year before, so treat this as a pattern of this year."
            ),
        }

    plan = None
    if chosen_name == "weekly_rhythm" and ctx["busy_week"] > 0:
        plan = {
            "weekly_everyday_allowance": _r(ctx["busy_week"]),
            "what": "A weekly ceiling for everyday spending, set at your own normal busy week, with a check-in each Sunday.",
            "check_in": check_in(cid, ctx["busy_week"]),
        }

    return {
        "customer_id": cid,
        "period": year.as_dict(),
        "usual_everyday_week": _r(ctx["usual_week"]),
        "normal_busy_week": _r(ctx["busy_week"]),
        "biggest_everyday_category": ctx["top_category"],
        "what_happened": {
            "days_below_zero": actual["days_below_zero_before"],
            "lowest_balance": _r(actual["lowest_before"]),
            "balance_today": _r(actual["end_before"]),
        },
        "levers": worthwhile[:3] if worthwhile else levers[:1],
        "levers_without_effect": [
            {"lever": entry["lever"], "title": entry["title"]} for entry in levers if entry["kept_over_the_year"] < 1
        ],
        "shown": chosen_entry,
        "does_it_hold": honesty,
        "plan": plan,
        "series": {
            "week_starts": [w.isoformat() for w in weeks],
            "lowest_balance_each_week": weekly_series(actual["low_by_week"]),
            "with_the_change": weekly_series(chosen["low_by_week"]),
        },
        "how_to_read": (
            "Your real payments with one rule applied. It assumes the money you did not spend stayed on the account. "
            "It is a replay of the past, not a forecast."
        ),
    }
