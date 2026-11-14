"""Mortgage readiness: what the bank looks at, and how far you are from it.

Everything here is learned from the 200 mortgage applications in the dataset
and from the customer's own transactions. It is education, not a credit
decision: it shows how an application like yours compares with the ones that
were approved, and which change would matter most.
"""

from __future__ import annotations

from functools import lru_cache

from . import db, periods
from .engine import EngineError, _pct, _r, customer


@lru_cache(maxsize=1)
def patterns() -> dict:
    """What the 200 applications in the data show."""
    overall = db.row(
        """
        SELECT
            count(*) AS applications,
            count(*) FILTER (WHERE final_decision = 'approved') AS approved,
            median(required_monthly_income / requested_loan) AS income_factor,
            median(collateral_value / property_price) AS collateral_share_of_price,
            median(property_price) AS median_price
        FROM mtg_final
        """
    )
    approved = db.row(
        """
        SELECT
            median(equity / property_price) AS equity_share_median,
            quantile_cont(equity / property_price, 0.25) AS equity_share_p25,
            quantile_cont(equity / property_price, 0.10) AS equity_share_p10,
            median(loan_to_value) AS ltv_median,
            median(property_price) AS price_median,
            median(requested_loan) AS loan_median,
            median(collateral_value / requested_loan) AS cover_median,
            quantile_cont(collateral_value / requested_loan, 0.25) AS cover_p25
        FROM mtg_final WHERE final_decision = 'approved'
        """
    )
    reasons = db.rows(
        """
        SELECT rejection_reason AS reason, count(*) AS n,
               median(equity / property_price) AS equity_share, median(loan_to_value) AS ltv
        FROM mtg_final WHERE final_decision = 'rejected' GROUP BY 1 ORDER BY 2 DESC
        """
    )
    costs = db.rows(
        """
        SELECT expense_type, count(DISTINCT mortgage_customer_id) AS applications, median(expense_amount) AS typical
        FROM mtg_events
        WHERE expense_type IS NOT NULL AND expense_amount > 0 AND expense_type <> 'existing_loan'
        GROUP BY 1 ORDER BY 3 DESC
        """
    )
    return {
        "applications": overall["applications"],
        "rejected": overall["applications"] - overall["approved"],
        # In the data the required monthly income is a fixed share of the loan.
        "income_factor": overall["income_factor"],
        "collateral_share_of_price": overall["collateral_share_of_price"],
        "approved": {
            "count": overall["approved"],
            "equity_share_median": approved["equity_share_median"],
            "equity_share_p25": approved["equity_share_p25"],
            "equity_share_p10": approved["equity_share_p10"],
            "ltv_median": approved["ltv_median"],
            "price_median": approved["price_median"],
            "loan_median": approved["loan_median"],
            "collateral_cover_median": approved["cover_median"],
            "collateral_cover_p25": approved["cover_p25"],
        },
        "rejections": [
            {"reason": r["reason"], "count": r["n"], "equity_share": r["equity_share"], "ltv": r["ltv"]} for r in reasons
        ],
        "typical_costs": [
            {"what": r["expense_type"], "typical": r["typical"], "seen_in_applications": r["applications"]} for r in costs
        ],
    }


MIN_DEFAULT_PRICE = 80000

REASON_TEXT = {
    "insufficient_collateral": "the collateral did not cover enough of the loan",
    "insufficient_income": "income was too low for the size of the loan",
    "insufficient_equity": "too little of the buyer's own money in the purchase",
    "existing_debt": "existing debt took too much of the income",
}


def _application(cid: str) -> dict | None:
    final = db.row("SELECT * FROM mtg_final WHERE customer_id = ?", [cid])
    if not final:
        return None
    events = db.rows(
        """
        SELECT event_ts, event_type, property_type, property_price_estimate, note
        FROM mtg_events WHERE mortgage_customer_id = ? ORDER BY event_ts
        """,
        [final["mortgage_customer_id"]],
    )
    counts: dict[str, int] = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    # The decision is not always the last event: a contact can follow it.
    decided = next((e for e in reversed(events) if e["event_type"] == "loan_decision"), None)
    properties = db.scalar(
        "SELECT count(DISTINCT property_id) FROM mtg_events WHERE mortgage_customer_id = ? AND property_id IS NOT NULL",
        [final["mortgage_customer_id"]],
    )
    return {
        "decision": final["final_decision"],
        "rejection_reason": final["rejection_reason"],
        "rejection_reason_plain": REASON_TEXT.get(final["rejection_reason"] or ""),
        "property_price": _r(final["property_price"], 0),
        "requested_loan": _r(final["requested_loan"], 0),
        "own_money": _r(final["equity"], 0),
        "own_money_share_pct": _pct(final["equity"], final["property_price"]),
        "loan_to_value_pct": _r(100 * final["loan_to_value"], 1),
        "collateral_value": _r(final["collateral_value"], 0),
        "monthly_income_the_bank_required": _r(final["required_monthly_income"], 0),
        "started": events[0]["event_ts"].date().isoformat() if events else None,
        "decided": decided["event_ts"].date().isoformat() if decided else None,
        "days": (decided["event_ts"] - events[0]["event_ts"]).days if decided else None,
        "properties_considered": properties,
        "times_in_contact_with_bank": counts.get("customer_contact", 0),
        "extra_collateral_requests": counts.get("additional_collateral_requested", 0),
        "timeline": [
            {"date": e["event_ts"].date().isoformat(), "event": e["event_type"], "note": e["note"]} for e in events
        ],
    }


def readiness(customer_id: str, property_price: float | None = None, own_money: float | None = None) -> dict:
    """How ready the customer is for a mortgage on a home of a given price.

    property_price: the home's price. Defaults to the customer's own
        application if there is one, otherwise the typical approved price.
    own_money: savings to put in (equity). Defaults to the application's
        equity, otherwise today's balance plus what was invested in the data.
    """
    cust = customer(customer_id)
    cid = cust["customer_id"]
    pat = patterns()
    app = _application(cid)

    money = db.row(
        """
        SELECT
            arg_max(balance_after, tx_ts) AS balance,
            coalesce(-sum(amount) FILTER (WHERE flow = 'to_savings'), 0)
              - coalesce(sum(amount) FILTER (WHERE flow = 'from_savings'), 0) AS net_invested
        FROM tx WHERE customer_id = ?
        """,
        [cid],
    )
    f = db.row("SELECT * FROM cust_features WHERE customer_id = ?", [cid])
    if not f:
        raise EngineError("Not enough history for this customer.")
    income = f["income"] or 0.0
    left_over = income - (f["spend"] or 0.0) - (f["transfer_out"] or 0.0)
    visible_savings = max(money["balance"] or 0.0, 0.0) + max(money["net_invested"] or 0.0, 0.0)

    if own_money is None:
        own_money = app["own_money"] if app else visible_savings
    if property_price is None:
        if app:
            property_price = app["property_price"]
        else:
            # Start from a home the customer's income could carry, so the first
            # view is about what is missing rather than a wall of "not yet".
            reach = (income / pat["income_factor"] if pat["income_factor"] else 0.0) + float(own_money)
            property_price = max(MIN_DEFAULT_PRICE, min(pat["approved"]["price_median"], reach // 5000 * 5000))
    property_price = float(property_price)
    if property_price <= 0:
        raise EngineError("property_price must be positive.")
    own_money = max(0.0, min(float(own_money), property_price))

    loan = property_price - own_money
    own_share = own_money / property_price
    required_income = loan * pat["income_factor"]
    max_loan = income / pat["income_factor"] if pat["income_factor"] else 0.0

    typical_share = pat["approved"]["equity_share_median"]
    low_share = pat["approved"]["equity_share_p10"]
    target_own_money = typical_share * property_price
    gap_typical = max(0.0, target_own_money - own_money)
    gap_income = max(0.0, required_income - income)
    # Own money needed so that the loan fits the income.
    own_money_for_income = max(0.0, property_price - max_loan)
    collateral = pat["collateral_share_of_price"] * property_price
    collateral_gap = max(0.0, loan - collateral)

    cover = collateral / loan if loan > 0 else 1.0
    cover_typical = pat["approved"]["collateral_cover_median"]
    cover_low = pat["approved"]["collateral_cover_p25"]

    def months_to(amount: float) -> float | None:
        """Months of saving at the customer's pace; None when over 50 years or no surplus."""
        if amount <= 0:
            return 0.0
        if left_over <= 0 or amount / left_over > 600:
            return None
        return _r(amount / left_over, 0)

    def level(ok: bool, close: bool) -> str:
        return "strong" if ok else ("close" if close else "not_yet")

    pillars = [
        {
            "pillar": "Income",
            "status": level(income >= required_income, income >= 0.9 * required_income),
            "you": f"EUR {income:,.0f} a month on average",
            "needed": f"EUR {required_income:,.0f} a month for a loan of EUR {loan:,.0f}",
            "explanation": (
                f"In the applications the bank required a monthly income of {100 * pat['income_factor']:.2f}% of the loan. "
                f"With your income the largest loan that fits is about EUR {max_loan:,.0f}."
            ),
        },
        {
            "pillar": "Your own money",
            "status": level(own_share >= typical_share, own_share >= low_share),
            "you": f"EUR {own_money:,.0f}, which is {100 * own_share:.0f}% of the price",
            "needed": f"approved buyers typically put in {100 * typical_share:.0f}% (EUR {target_own_money:,.0f} here)",
            "explanation": (
                f"Nine in ten approved buyers put in at least {100 * low_share:.0f}%. "
                "The more of your own money, the smaller the loan and the easier every other check."
            ),
        },
        {
            "pillar": "Collateral",
            "status": level(cover >= cover_typical, cover >= cover_low),
            "you": f"the home would cover about {100 * min(cover, 1.0):.0f}% of a EUR {loan:,.0f} loan",
            "needed": f"in approved applications the collateral typically covered {100 * cover_typical:.0f}% of the loan",
            "explanation": (
                f"A home typically counts as collateral for {100 * pat['collateral_share_of_price']:.0f}% of its price "
                f"(EUR {collateral:,.0f} here). The rest needs extra collateral, a guarantee, or more of your own money. "
                "Too little collateral was the most common reason for rejection in the data."
            ),
        },
        {
            "pillar": "Money habits",
            "status": level(
                f["overdraft_days"] == 0 and left_over > 0,
                f["overdraft_days"] <= 10 and left_over > 0,
            ),
            "you": f"EUR {left_over:,.0f} left over a month, {f['overdraft_days']} days below zero in the last year",
            "needed": "a steady surplus and no days below zero",
            "explanation": "A bank reads your account the way this app does. A surplus every month is what pays the loan.",
        },
    ]

    changes = []
    if gap_income > 0:
        changes.append(
            {
                "change": f"Bring EUR {own_money_for_income - own_money:,.0f} more of your own money, or look at homes up to about EUR {max_loan + own_money:,.0f}",
                "why": f"The loan is EUR {loan - max_loan:,.0f} larger than your income supports.",
                "months_at_your_saving_pace": months_to(own_money_for_income - own_money),
            }
        )
    if gap_typical > 0:
        changes.append(
            {
                "change": f"Save EUR {gap_typical:,.0f} more to reach the typical {100 * typical_share:.0f}% of your own money",
                "why": f"You are at {100 * own_share:.0f}%.",
                "months_at_your_saving_pace": months_to(gap_typical),
            }
        )
    if cover < cover_low and collateral_gap > 0:
        changes.append(
            {
                "change": f"Cover a collateral gap of about EUR {collateral_gap:,.0f}",
                "why": "With more own money, extra collateral or a guarantee the loan fits the home's collateral value.",
                "months_at_your_saving_pace": months_to(collateral_gap),
            }
        )
    if f["overdraft_days"] > 0 or left_over <= 0:
        changes.append(
            {
                "change": "Get to a steady monthly surplus with no days below zero",
                "why": f"{f['overdraft_days']} days below zero and {f['negative_months']} months where more went out than came in during the last year.",
                "months_at_your_saving_pace": None,
            }
        )

    strong = sum(1 for p in pillars if p["status"] == "strong")
    return {
        "customer_id": cid,
        "note": "This compares your situation with the applications in the data. It is guidance, not a credit decision.",
        "home": {
            "property_price": _r(property_price, 0),
            "own_money": _r(own_money, 0),
            "loan": _r(loan, 0),
            "own_money_share_pct": _r(100 * own_share, 1),
            "loan_to_value_pct": _r(100 * loan / property_price, 1),
        },
        "you": {
            "monthly_income": _r(income, 0),
            "monthly_left_over": _r(left_over, 0),
            "balance_today": _r(money["balance"], 0),
            "invested_during_the_data_period": _r(max(money["net_invested"] or 0.0, 0.0), 0),
            "largest_loan_your_income_supports": _r(max_loan, 0),
            "price_range_with_this_own_money": _r(max_loan + own_money, 0),
        },
        "readiness": f"{strong} of {len(pillars)} checks look strong",
        "pillars": pillars,
        "what_would_matter_most": changes[:3],
        "other_costs_to_plan_for": [
            {"what": c["what"].replace("_", " "), "typical": _r(c["typical"], 0), "seen_in_applications": c["seen_in_applications"]}
            for c in pat["typical_costs"]
        ],
        "learned_from": {
            "applications": pat["applications"],
            "approved": pat["approved"]["count"],
            "rejections": [
                {"reason": REASON_TEXT.get(r["reason"], r["reason"]), "count": r["count"]} for r in pat["rejections"]
            ],
        },
        "your_application": {k: v for k, v in app.items() if k != "timeline"} if app else None,
    }


def application_timeline(customer_id: str) -> dict:
    """The customer's own mortgage application, step by step."""
    cid = customer(customer_id)["customer_id"]
    app = _application(cid)
    if not app:
        return {"customer_id": cid, "has_application": False, "note": "No mortgage application in the data for this customer."}
    return {"customer_id": cid, "has_application": True, **app}
