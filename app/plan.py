"""Looking ahead: a plan for the next salary, and the balance until the payday after next.

Both are arithmetic on the customer's own usual pattern: salary on its usual day, bills on
their usual days at their six-month average, shopping at the pace of the last 90 days. They
are not forecasts of what will happen. They show what the next weeks look like if they go
like the usual ones, so the customer can act before trouble instead of after it.
"""

from __future__ import annotations

import calendar
import datetime as dt

from . import baskets, db, engine
from .engine import EngineError, _next_day_of_month, _pct, _r

THIN_DAYS = 7  # a lowest point under a week of usual shopping counts as "thin"
HOW_TO_READ = (
    "A projection of your usual pattern, not a forecast: salary on its usual day, bills on their usual days at "
    "their six-month average, and shopping at your pace of the last 90 days. Unexpected costs are not in it."
)


def _pattern(cid: str, today: dt.date) -> dict:
    """The customer's usual month: payday, bills by day of month, shopping per day, balance today."""
    monthly = {tx_type: float(habit["a_month"]) for tx_type, habit in engine.bill_habits(cid, today).items()}
    pace = db.row(
        """
        SELECT
            coalesce(-sum(amount) FILTER (WHERE basket = 'essentials' AND tx_type = 'purchase'), 0) / 90.0 AS essentials_per_day,
            coalesce(-sum(amount) FILTER (WHERE basket = 'everyday'), 0) / 90.0 AS everyday_per_day
        FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
        """,
        [cid, today - dt.timedelta(days=89), today],
    )
    balance = db.scalar(
        "SELECT arg_max(balance_after, tx_ts) FROM tx WHERE customer_id = ? AND tx_date <= ?", [cid, today]
    ) or 0.0
    return {
        "payday": engine._payday(cid, today),
        "monthly": monthly,
        "essentials_per_day": float(pace["essentials_per_day"]),
        "everyday_per_day": float(pace["everyday_per_day"]),
        "balance": float(balance),
    }


def _payday_on_or_before(day: dt.date, day_of_month: int) -> dt.date:
    """The latest date on or before `day` that falls on the usual payday of the month."""
    year, month = day.year, day.month
    for _ in range(3):
        candidate = dt.date(year, month, min(day_of_month, calendar.monthrange(year, month)[1]))
        if candidate <= day:
            return candidate
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    raise RuntimeError("could not find the previous payday")


def _project(pattern: dict, bills: dict, start: dt.date, end: dt.date, paydays: set[dt.date], everyday_per_day: float) -> list[tuple[dt.date, float]]:
    """The balance at the end of each day: salary in, dated bills out, and the daily rates."""
    on_day: dict[dt.date, float] = {}
    for b in bills["dated"]:
        on_day[b["date"]] = on_day.get(b["date"], 0.0) + b["amount"]
    balance = pattern["balance"]
    salary = pattern["payday"]["expected_amount"] if pattern["payday"] else 0.0
    out = []
    day = start
    while day <= end:
        if day in paydays:
            balance += salary
        balance -= on_day.get(day, 0.0) + bills["per_day_total"]
        balance -= pattern["essentials_per_day"] + everyday_per_day
        out.append((day, balance))
        day += dt.timedelta(days=1)
    return out


def outlook(customer_id: str) -> dict:
    """The balance day by day until the payday after next, if the coming weeks go like the usual ones."""
    cid = engine.customer(customer_id)["customer_id"]
    today = db.today()
    p = _pattern(cid, today)
    payday = p["payday"]
    start = today + dt.timedelta(days=1)
    if payday:
        first = payday["next"]
        second = _next_day_of_month(first, payday["day_of_month"])
        end = second - dt.timedelta(days=1)
        paydays = {first, second}
    else:
        end = today + dt.timedelta(days=35)
        paydays = set()

    usual = p["everyday_per_day"]
    bills = engine.expected_bills(cid, today, start, end)
    path = _project(p, bills, start, end, paydays, usual)
    low_day, low = min(path, key=lambda x: x[1])
    below = [(d, b) for d, b in path if b < -0.005]
    per_day = p["essentials_per_day"] + usual

    result: dict = {
        "customer_id": cid,
        "as_of": today.isoformat(),
        "until": end.isoformat(),
        "days": len(path),
        "balance_today": _r(p["balance"]),
        "next_payday": payday["next"].isoformat() if payday else None,
        "assumes": {
            "salary": _r(payday["expected_amount"]) if payday else None,
            "bills": [
                {"what": b["what"], "date": b["date"].isoformat(), "amount": _r(b["amount"]), "overdue": b["late"]}
                for b in bills["dated"]
            ],
            "other_bills_a_day": _r(bills["per_day_total"]),
            "groceries_and_transport_a_day": _r(p["essentials_per_day"]),
            "everyday_spending_a_day": _r(usual),
        },
        "lowest_point": {"date": low_day.isoformat(), "balance": _r(low), "in_days": (low_day - today).days},
        "status": "short" if below else "thin" if low < THIN_DAYS * per_day else "fine",
        "how_to_read": HOW_TO_READ,
    }
    series = {"dates": [d.isoformat() for d, _ in path], "balance": [_r(b) for _, b in path]}

    if below:
        first_below = below[0][0]
        short_by = -low  # how far below zero the deepest day in the whole stretch is

        # Which bill tips it: the largest dated bill before the balance first crosses zero.
        before = [b for b in bills["dated"] if b["date"] <= first_below]
        tipping = None
        if before:
            b = max(before, key=lambda b: b["amount"])
            tipping = {"what": b["what"], "date": b["date"].isoformat(), "amount": _r(b["amount"]), "overdue": b["late"]}

        heads_up: dict = {
            "below_zero_from": first_below.isoformat(),
            "in_days": (first_below - today).days,
            "days_below_zero": len(below),
            "out_of_the_days_shown": len(path),
            "deepest_point": {"date": low_day.isoformat(), "balance": _r(low)},
            "short_by": _r(short_by),
            "biggest_bill_before": tipping,
        }
        # The fix the customer controls: a lower everyday pace from tomorrow. It has to be low
        # enough for every day below zero, not only the deepest one.
        cut = max(-b / max((d - today).days, 1) for d, b in below)
        ceiling = usual - cut
        if ceiling >= 0:
            ceiling = int(ceiling * 100) / 100  # round down, so the plan really stays above zero
            fixed = _project(p, bills, start, end, paydays, ceiling)
            heads_up["fix"] = {
                "everyday_spending_a_day": _r(ceiling),
                "instead_of_your_usual": _r(usual),
                "a_week": _r(ceiling * 7),
                "instead_of_a_week": _r(usual * 7),
                "hold_it_until": end.isoformat(),
                "lowest_point_then": _r(min(b for _, b in fixed)),
            }
            series["with_the_fix"] = [_r(b) for _, b in fixed]
        else:
            # With no everyday spending at all, every day gains what it would have cost so far.
            bare = min(b + usual * (d - today).days for d, b in path)
            heads_up["fix"] = None
            heads_up["everyday_spending_alone_is_not_enough"] = {
                "still_short_by": _r(max(0.0, -bare)),
                "why": "Even with no everyday spending at all until then, the bills and groceries come to more than the money available.",
            }
        deposit = p["monthly"].get("investment_deposit", 0.0)
        if deposit >= 1:
            # One deposit falls in each month of the stretch; pausing them is the other lever.
            heads_up["or_pause"] = {
                "what": engine.COMMITTED_TYPES["investment_deposit"],
                "a_month": _r(deposit),
                "covers_it": sum(b["amount"] for b in bills["dated"] if b["tx_type"] == "investment_deposit") >= short_by,
            }
        result["heads_up"] = heads_up

    result["series"] = series
    return result


def payday_plan(customer_id: str, savings_goal_pct: float = engine.DEFAULT_SAVINGS_GOAL_PCT) -> dict:
    """A split of the next salary into the three baskets and savings, ready to accept.

    The same budget as "safe to spend", laid out for the pay period that starts on the next payday,
    next to what actually happened in the last full pay period.
    """
    cid = engine.customer(customer_id)["customer_id"]
    savings_goal_pct = max(0.0, min(float(savings_goal_pct), 60.0))
    today = db.today()
    p = _pattern(cid, today)
    payday = p["payday"]
    if not payday:
        raise EngineError("There is no regular salary in the data, so there is no payday to plan for.")

    start = payday["next"]
    following = _next_day_of_month(start, payday["day_of_month"])
    days = max((following - start).days, 1)
    salary = float(payday["expected_amount"])
    monthly = p["monthly"]
    housing = monthly.get("housing_payment", 0.0)
    utilities = monthly.get("utilities_payment", 0.0)
    transfer = monthly.get("salary_sweep", 0.0)
    automatic = monthly.get("investment_deposit", 0.0)
    shopping = p["essentials_per_day"] * days
    unexpected_month = float((db.row("SELECT unexpected FROM cust_avg WHERE customer_id = ?", [cid]) or {}).get("unexpected") or 0.0)
    buffer = unexpected_month * days / 30.4375

    # When the salary does not stretch, things give way in this order: everyday spending and
    # savings first, then the buffer for the unexpected. Essentials are never cut: if they alone
    # are more than the salary, the plan says how much is missing.
    wanted = max(salary * savings_goal_pct / 100.0, automatic)
    after_essentials = salary - housing - utilities - transfer - shopping
    short_by = max(0.0, -after_essentials)
    full_buffer = buffer
    buffer = max(0.0, min(buffer, after_essentials))
    left = max(0.0, after_essentials - buffer)
    saving = min(wanted, left)
    everyday = left - saving

    def line(key: str, amount: float, **extra) -> dict:
        row = {"key": key, "amount": _r(amount), "share_of_salary_pct": _pct(amount, salary)}
        if key in baskets.BASKETS:
            row["basket"] = baskets.BASKETS[key]["name"]
        row.update(extra)
        return row

    parts = [
        {"label": label, "amount": _r(amount)}
        for label, amount in (
            ("Housing payment", housing),
            ("Utility bills", utilities),
            ("Groceries and transport at your usual pace", shopping),
        )
        if amount >= 1
    ]
    split = [line("essentials", housing + utilities + shopping, parts=parts)]
    if transfer >= 1:
        split.append(line("transfer", transfer, label="Regular transfer to another account"))
    split.append(
        line(
            "unexpected",
            buffer,
            note="Your 12-month monthly average, set aside for repairs, health and replacements.",
            usual=_r(full_buffer),
            kept_in_full=buffer >= full_buffer - 0.005,
        )
    )
    split.append(
        line(
            "savings",
            saving,
            label="Savings",
            goal_pct=savings_goal_pct,
            goal_kept=saving >= wanted - 0.005,
            already_automatic=_r(min(automatic, saving)),
            # What is not already a regular investment deposit would go to the bank's saving service.
            to="Säästäjä" if saving - min(automatic, saving) >= 0.005 else None,
        )
    )
    split.append(line("everyday", everyday, a_week=_r(everyday / days * 7), a_day=_r(everyday / days)))

    # What actually happened in the last full pay period, for comparison. The period runs from
    # the usual payday to the day before the next one, also when a salary arrived late or early,
    # so it is always about a month and can be set next to the plan.
    this_period = _payday_on_or_before(today, payday["day_of_month"])
    finish = this_period - dt.timedelta(days=1)
    begin = _payday_on_or_before(finish, payday["day_of_month"])
    last = None
    if begin >= engine.data_start():
        got = db.row(
            """
            SELECT
                coalesce(-sum(amount) FILTER (WHERE flow = 'spend' AND basket = 'essentials'), 0) AS essentials,
                coalesce(-sum(amount) FILTER (WHERE flow = 'spend' AND basket = 'unexpected'), 0) AS unexpected,
                coalesce(-sum(amount) FILTER (WHERE flow = 'spend' AND basket = 'everyday'), 0) AS everyday,
                coalesce(-sum(amount) FILTER (WHERE tx_type = 'investment_deposit'), 0) AS saved
            FROM tx WHERE customer_id = ? AND tx_date BETWEEN ? AND ?
            """,
            [cid, begin, finish],
        )
        last = {
            "from": begin.isoformat(),
            "to": finish.isoformat(),
            "days": (finish - begin).days + 1,
            "essentials": _r(got["essentials"]),
            "unexpected": _r(got["unexpected"]),
            "everyday": _r(got["everyday"]),
            "saved": _r(got["saved"]),
        }
        # Said in words, so nobody has to guess what a minus sign means.
        gap = float(got["everyday"]) - everyday
        if gap >= 0:
            last["everyday_then_was_more_than_this_plan_by"] = _r(gap)
        else:
            last["this_plan_has_more_for_everyday_by"] = _r(-gap)

    result = {
        "customer_id": cid,
        "as_of": today.isoformat(),
        "payday": {"date": start.isoformat(), "in_days": (start - today).days, "expected_salary": _r(salary)},
        "pay_period": {"from": start.isoformat(), "to": (following - dt.timedelta(days=1)).isoformat(), "days": days},
        "savings_goal_pct": savings_goal_pct,
        "split": split,
        "adds_up_to": _r(sum(row["amount"] for row in split)),
        "fits": short_by < 0.005,
        # "tight": the salary covers the essentials, but leaves nothing for everyday spending.
        "tight": short_by < 0.005 and everyday < 0.005,
        "essentials_share_of_salary_pct": _pct(housing + utilities + transfer + shopping, salary),
        "last_pay_period": last,
        "what_accepting_does": "In this demo, accepting only saves the plan. In the bank's app it would set the transfer to savings and the everyday budget for the pay period.",
        "how_to_read": "Essentials first, then a buffer for the unexpected, then savings, and everyday spending is what is left.",
    }
    if short_by >= 0.005:
        result["short_by"] = _r(short_by)
        result["why_it_does_not_fit"] = "The regular essentials alone come to more than the expected salary."
    elif result["tight"]:
        result["why_it_is_tight"] = (
            "Regular essentials take almost all of this salary, so the plan has nothing for everyday spending. "
            "Anything you spend on it comes out of the balance you already have."
        )
    return result
