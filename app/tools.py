"""The tools the model can call.

Each tool is a thin wrapper around one engine function. The customer_id is
never an argument: the server injects the signed-in customer, so the model
cannot ask for anyone else's data.
"""

from __future__ import annotations

from typing import Any, Callable

from . import baskets, bills, engine, explore, insights, mortgage, periods, plan, replay
from .engine import EngineError

PERIOD_DOC = (
    "Named period: " + ", ".join(periods.PERIOD_NAMES) + ". Also 'last_N_days', 'last_N_months', "
    "a month as 'YYYY-MM' or a year as 'YYYY'. Ignored when start and end are given."
)
CATEGORY_DOC = "One of: " + ", ".join(baskets.SPEND_CATEGORIES) + "."
SUBCATEGORY_DOC = (
    "The kind of place, finer than a category. Use it only when the customer names a kind of place; for a "
    "whole category (groceries or food shopping, restaurants or eating out, transport, health, travel) use "
    "category instead. Plain words work and cover every matching kind of shop: 'fast food', 'clothes' (all "
    "clothing shops), 'fuel', 'taxis', 'bars', 'pharmacy'. Also: Public transport, Parking, Doctors, Dentists, "
    "Electronics, Furniture, Airlines, Hotels, Cinemas, Book stores, Sporting goods, Utility bills, Housing "
    "payment. Use it on its own, without category."
)
BASKET_DOC = "One of the three baskets: essentials, unexpected, everyday."
TARGET_DOC = "A basket (essentials, unexpected, everyday), a category or a subcategory, e.g. 'Restaurants' or 'Taxis'."

_FILTERS = {
    "period": {"type": "string", "description": PERIOD_DOC},
    "start": {"type": "string", "description": "Start date YYYY-MM-DD (optional, overrides period)."},
    "end": {"type": "string", "description": "End date YYYY-MM-DD (optional)."},
    "category": {"type": "string", "description": CATEGORY_DOC},
    "subcategory": {"type": "string", "description": SUBCATEGORY_DOC},
    "basket": {"type": "string", "description": BASKET_DOC},
    "min_amount": {"type": "number", "description": "Only payments of at least this many euros."},
    "max_amount": {"type": "number", "description": "Only payments of at most this many euros."},
}


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


TOOL_SPECS = [
    _fn(
        "get_spending",
        "Total spending in a period, optionally filtered by category, subcategory or basket, and optionally "
        "broken down. Use for 'how much did I spend on X', 'where did my money go', trends over months, "
        "and comparisons with the previous period (returned automatically).",
        {
            **_FILTERS,
            "group_by": {
                "type": "string",
                "enum": list(engine.GROUPINGS),
                "description": "Break the total down by this.",
            },
        },
    ),
    _fn(
        "list_transactions",
        "List individual payments (date, amount, what), newest first or largest first, with their count and "
        "total. The app shows the list itself, so do not write the payments out in your answer.",
        {
            **_FILTERS,
            "sort": {"type": "string", "enum": ["date", "amount"]},
            "limit": {"type": "integer", "description": "How many to list, at most 50."},
        },
    ),
    _fn(
        "get_baskets",
        "The three-basket view of a period: Regular essentials, Unexpected necessities and Everyday spending, "
        "with totals, shares, the top items in each, income, what was left over, and the small everyday "
        "purchases that slip through the fingers. Use for 'where does my money really go'.",
        {k: _FILTERS[k] for k in ("period", "start", "end")},
    ),
    _fn(
        "get_cashflow",
        "Month by month: income, the three baskets, savings, net and end balance. Use for trends and "
        "'did I spend more than I earned'.",
        {"months": {"type": "integer", "description": "How many recent complete months, 1 to 24. Default 6."}},
    ),
    _fn(
        "get_safe_to_spend",
        "What is safe to spend on everyday things until the next payday and for the rest of this week, with "
        "the full pay-period budget behind it, plus safe-to-save guidance. Use for 'what can I spend this "
        "week', 'can I afford X', 'how much can I save'.",
        {"savings_goal_pct": {"type": "number", "description": "Share of salary to save. Default 10."}},
    ),
    _fn(
        "check_affordability",
        "Whether one specific purchase fits right now and what it would leave: an everyday purchase against "
        "what is safe to spend this week and until payday, a necessity against the unexpected buffer and the "
        "balance. Use for 'can I afford this?', also when the customer sends a photo of a price tag, a product, "
        "a receipt or a bill: read the price from the photo and pass it as amount. A large Home & Tech or "
        "transport purchase comes back with two readings: as a necessity (fits, why) and as a treat "
        "(if_it_is_a_treat), because the price alone cannot tell which it is. When it does not fit now, the result "
        "also says when it could ('when'): from the next payday, or by changing one habit. So use this for 'when can I "
        "afford it', 'how long do I have to wait' and 'how could I make it fit' too, with the same amount.",
        {
            "amount": {"type": "number", "description": "The price in euros."},
            "what": {
                "type": "string",
                "description": "A few words for the item, e.g. 'running shoes'. From a photo: the item's name exactly as written on it, not translated.",
            },
            "category": {
                "type": "string",
                "description": "The spending category of the item. " + CATEGORY_DOC + " Clothes, shoes, books and sports "
                "gear are Lifestyle; electronics, furniture and tools are Home & Tech.",
            },
        },
        ["amount"],
    ),
    _fn(
        "prepare_payment",
        "Prepare a payment from a bill or an invoice the customer photographed: pass what is printed on it, and the "
        "result is a draft for the customer to check. It recalculates the check digits inside the account number "
        "(IBAN) and the reference number, so a misread digit is caught, and says whether the balance covers the "
        "bill. Use when the photo is a bill to pay (it names a payee and an account number). You never pay: the "
        "customer confirms the draft in the app.",
        {
            "amount": {
                "type": "number",
                "description": "The total to pay in euros: the figure printed next to the words for the total (Maksettava yhteensä, "
                "Yhteensä, Att betala, Amount due). Never one line of the bill.",
            },
            "payee": {"type": "string", "description": "Who the bill is from, exactly as printed."},
            "iban": {
                "type": "string",
                "description": "The payee's account number (IBAN), copied character by character. Never correct, complete or guess a character.",
            },
            "reference": {"type": "string", "description": "The reference number, copied digit by digit. Leave it out if the bill has none."},
            "due_date": {
                "type": "string",
                "description": "The due date exactly as the bill prints it, for example 10.12.2026 or 24 December 2026. Do not convert it "
                "to another format: the app reads it.",
            },
            "bill_date": {
                "type": "string",
                "description": "The bill's own date (when it was written: Laskun päivämäärä, Fakturadatum, Invoice date), exactly as printed. "
                "It is not the due date.",
            },
            "category": {"type": "string", "description": "What kind of bill it is, if clear: an electricity, water, phone or internet bill is Utilities. " + CATEGORY_DOC},
        },
        ["amount"],
    ),
    _fn(
        "simulate_change",
        "What-if: the effect of changing one kind of spending by a percentage, based on the last 6 months. "
        "Use for 'how much would I save if I cut dining out by 20%'.",
        {
            "target": {"type": "string", "description": TARGET_DOC},
            "change_pct": {"type": "number", "description": "Change in percent. -20 means spend 20% less."},
            "months": {"type": "integer", "description": "Horizon in months for the total saving. Default 12."},
        },
        ["target", "change_pct"],
    ),
    _fn(
        "replay_year",
        "Replay the customer's own last 12 months with one habit changed and show what would have been "
        "different: money kept, days below zero, balance today. Also ranks the customer's three biggest levers "
        "and says whether the top one was the same the year before. Use for 'what would have helped', 'what "
        "should I change', 'how could I save more', 'what if I had spent less'. It is a replay of the past, "
        "not a forecast: say so.",
        {
            "lever": {
                "type": "string",
                "enum": replay.LEVERS,
                "description": "Which habit to change. Leave empty to show the one that would have kept the most.",
            }
        },
    ),
    _fn(
        "get_payday_plan",
        "A plan for the next salary: how to split it into regular essentials, a buffer for the unexpected, "
        "savings and everyday spending, next to what the last pay period really looked like. Use for 'how "
        "should I split my salary', 'make me a budget', 'plan my payday', 'how much should I save each month'. "
        "The customer accepts the plan in the app; you never move money.",
        {"savings_goal_pct": {"type": "number", "description": "Share of salary to save. Default 10."}},
    ),
    _fn(
        "get_balance_outlook",
        "Looks ahead: the balance day by day until the payday after next if the coming weeks go like the "
        "customer's usual ones (salary and monthly bills on their usual days, shopping at the usual pace). "
        "Says whether and when the balance would go below zero, which bill comes before that, and the level "
        "of everyday spending that avoids it. Use for 'will my money last until payday', 'am I going to run "
        "short', 'which bills are coming', 'when is my rent due'. It is the usual pattern projected forward, "
        "not a forecast: say so.",
        {},
    ),
    _fn(
        "get_spender_profile",
        "What kind of spender the customer is: a spender type with the rule behind it, basket shares, habits "
        "(small purchases, big purchases, weekends, days below zero) and how they compare with peers of the same age.",
        {},
    ),
    _fn(
        "compare_with_peers",
        "Compare the customer's monthly average with other customers (same age group by default). Leave "
        "target empty for an overview of the three baskets, income and share of income left over.",
        {
            "target": {
                "type": "string",
                "description": TARGET_DOC + " Or a metric: income, spending, savings_rate, everyday_share.",
            },
            "peer_group": {"type": "string", "enum": list(insights.PEER_GROUPS)},
        },
    ),
    _fn(
        "get_highlights",
        "What stands out in the customer's money right now: over budget, a category above its usual level, an "
        "unexpected expense, small purchases adding up, idle cash, days below zero. Use for open questions like "
        "'anything I should know?', 'how am I doing?' or 'how could I save more?'.",
        {},
    ),
    _fn(
        "get_regular_payments",
        "Regular income and regular payments (salary, housing, utilities, investment deposits) with the usual "
        "day of month, amount and next expected date.",
        {},
    ),
    _fn(
        "get_mortgage_readiness",
        "How ready the customer is to get a mortgage for a home of a given price: income, own money, "
        "collateral and money habits compared with 200 real application outcomes, and the changes that would "
        "matter most. Guidance, not a credit decision.",
        {
            "property_price": {"type": "number", "description": "Price of the home in euros (optional)."},
            "own_money": {"type": "number", "description": "Savings the customer would put in, in euros (optional)."},
        },
    ),
    _fn(
        "get_mortgage_application",
        "The customer's own mortgage application in the data, if any: outcome, reason and the timeline of events.",
        {},
    ),
    _fn(
        "run_sql",
        "Free exploration: run one read-only DuckDB SELECT over the table my_transactions, which holds only "
        "this customer's rows. Columns: date, time, amount (negative = out), spent (positive euros out), "
        "category, subcategory, basket, flow, type, merchant_id, mcc, balance_after. Use only when no other "
        "tool can answer the question.",
        {"sql": {"type": "string", "description": "A single SELECT statement."}},
        ["sql"],
    ),
    _fn(
        "explain_baskets",
        "The three baskets and the exact rules that decide which basket a payment falls into.",
        {},
    ),
]

_HANDLERS: dict[str, Callable[..., dict]] = {
    "get_spending": engine.spending,
    "list_transactions": engine.transactions,
    "get_baskets": engine.basket_summary,
    "get_cashflow": engine.cashflow,
    "get_safe_to_spend": engine.safe_to_spend,
    "check_affordability": plan.can_afford,
    "prepare_payment": bills.payment_draft,
    "simulate_change": engine.what_if,
    "replay_year": replay.replay,
    "get_payday_plan": plan.payday_plan,
    "get_balance_outlook": plan.outlook,
    "get_spender_profile": insights.spender_profile,
    "compare_with_peers": insights.benchmark,
    "get_highlights": insights.notices,
    "get_regular_payments": engine.recurring,
    "get_mortgage_readiness": mortgage.readiness,
    "get_mortgage_application": mortgage.application_timeline,
    "run_sql": explore.run,
    "explain_baskets": lambda customer_id: engine.basket_rules(),
}

TOOL_NAMES = list(_HANDLERS)


def _allowed_args(name: str) -> set[str]:
    spec = next(s for s in TOOL_SPECS if s["function"]["name"] == name)
    return set(spec["function"]["parameters"]["properties"])


def call(customer_id: str, name: str, arguments: dict[str, Any] | None, extra: dict[str, Any] | None = None) -> dict:
    """Run a tool for a customer. Problems come back as {"error": ...} so the model can correct itself.

    extra is what the app itself adds to a call. The model cannot pass it: its arguments are
    checked against the tool's own list first.
    """
    if name not in _HANDLERS:
        return {"error": f"Unknown tool '{name}'. Available: {', '.join(TOOL_NAMES)}."}
    args = {k: v for k, v in (arguments or {}).items() if v is not None and v != ""}
    unknown = set(args) - _allowed_args(name)
    if unknown:
        return {"error": f"Unknown argument(s) for {name}: {', '.join(sorted(unknown))}."}
    try:
        return _HANDLERS[name](customer_id, **args, **(extra or {}))
    except EngineError as exc:
        return {"error": str(exc)}
    except (TypeError, ValueError) as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
