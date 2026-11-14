"""Keyword router: answers the common questions without a language model.

It picks one tool from keywords in the question and fills a fixed sentence
with the tool's numbers. It is the fallback when no model is configured or
reachable, and the baseline the model is measured against.
"""

from __future__ import annotations

import re
import time
from typing import Iterator

from . import baskets, db, engine, tools

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]

_PERIOD_PHRASES = [
    (r"\btoday\b", "today"),
    (r"\byesterday\b", "yesterday"),
    (r"\bthis week\b", "this_week"),
    (r"\blast week\b", "last_week"),
    (r"\bthis month\b", "this_month"),
    (r"\blast month\b", "last_month"),
    (r"\bthis year\b", "this_year"),
    (r"\blast year\b", "last_year"),
    (r"\b(all time|ever|in total)\b", "all_time"),
]


def eur(value) -> str:
    value = float(value or 0)
    return f"EUR {value:,.0f}" if abs(value) >= 100 else f"EUR {value:,.2f}"


def find_period(text: str) -> str | None:
    for pattern, name in _PERIOD_PHRASES:
        if re.search(pattern, text):
            return name
    match = re.search(r"\b(?:last|past)\s+(\d+|three|six|twelve)\s+(day|week|month|year)s?\b", text)
    if match:
        words = {"three": 3, "six": 6, "twelve": 12}
        n = words.get(match.group(1)) or int(match.group(1))
        unit = match.group(2)
        if unit == "day":
            return f"last_{n}_days"
        if unit == "week":
            return f"last_{n * 7}_days"
        if unit == "year":
            return f"last_{n * 12}_months"
        return f"last_{n}_months"
    for index, name in enumerate(MONTHS, start=1):
        if re.search(rf"\b{name}\b", text):
            today = db.today()
            year = today.year if index <= today.month else today.year - 1
            return f"{year}-{index:02d}"
    return None


def find_target(text: str) -> str | None:
    """The first basket, category or subcategory mentioned in the text."""
    candidates: list[str] = []
    candidates += list(engine.SUBCATEGORY_ALIASES)
    candidates += [s.lower() for s in engine.subcategories()]
    candidates += list(engine.CATEGORY_ALIASES)
    candidates += [c.lower() for c in baskets.SPEND_CATEGORIES]
    candidates += [k for k in engine.BASKET_ALIASES if k not in ("regular", "fixed")]
    best = None
    for word in candidates:
        match = re.search(rf"\b{re.escape(word)}\b", text)
        if match and (best is None or len(word) > len(best)):
            best = word
    return best


def _numbers(text: str) -> list[float]:
    return [float(n.replace(",", "").replace(" ", "")) for n in re.findall(r"\d[\d, ]*(?:\.\d+)?", text)]


def route(message: str) -> tuple[str, dict]:
    """Choose a tool and its arguments from the words in the message."""
    text = " " + message.lower().strip() + " "
    period = find_period(text)
    target = find_target(text)
    numbers = _numbers(text)

    if re.search(r"mortgage|home loan|asuntolaina|bol[åa]n|buy (a|an) (home|house|flat|apartment)", text):
        if re.search(r"my application|what happened|why was i|timeline", text):
            return "get_mortgage_application", {}
        price = next((n for n in numbers if n >= 30000), None)
        return "get_mortgage_readiness", ({"property_price": price} if price else {})
    if re.search(r"what if|if i (cut|reduce|spen[dt]|lower|halve)|reduc|cut (back|down)|\d+\s?% (less|more)", text) and target:
        pct = next((n for n in numbers if 0 < n <= 100), 20.0)
        sign = 1 if re.search(r"\b(more|increase|raise)\b", text) else -1
        return "simulate_change", {"target": target, "change_pct": sign * pct}
    if re.search(r"payday plan|plan (for )?my (salary|pay|payday)|split my (salary|pay)|make me a budget|budget for (the )?next", text):
        return "get_payday_plan", {}
    if re.search(r"run(ning|s)? (short|out)|last until payday|money last|bills? (are )?(coming|due)|heads.?up|go(es)? below zero|when is my rent", text):
        return "get_balance_outlook", {}
    if re.search(r"afford|can i buy|should i buy|ok to buy", text):
        price = next((n for n in numbers if n >= 1), None)
        if price:
            args = {"amount": price}
            if target and engine.resolve_target(target)["type"] == "category":
                args["category"] = engine.resolve_target(target)["label"]
            return "check_affordability", args
    if re.search(r"safe|afford|can i spend|how much can i|left to spend|this week", text) and not re.search(r"spent|did i spend", text):
        return "get_safe_to_spend", {}
    if re.search(r"should know|how am i doing|stands? out|worth a look|highlights|cannot see|can you not see|another bank|other bank", text):
        return "get_highlights", {}
    if re.search(r"kind of spender|type of spender|spender am i|my habits|profile|describe me", text):
        return "get_spender_profile", {}
    if re.search(r"compare|compared|others|other people|peers|people like me|average person|normal|typical", text):
        return "compare_with_peers", ({"target": target} if target else {})
    if re.search(r"replay|would have helped|what should i change|if i had|biggest lever|levers?\b|save more|how (can|could) i save|start saving|saving tips", text):
        return "replay_year", {}
    if re.search(r"which basket|basket rules|how do you (classify|decide)|what are the (three )?baskets", text):
        return "explain_baskets", {}
    if re.search(r"where (did|does|has) (all )?my money|basket|overview|breakdown|summary|slip", text):
        return "get_baskets", ({"period": period} if period else {})
    if re.search(r"payday|salary|regular|recurring|subscription|bills due|standing", text) and not target:
        return "get_regular_payments", {}
    if re.search(r"month by month|trend|more than i earn|cash ?flow|income and", text):
        return "get_cashflow", {}
    if re.search(r"\b(show|list|biggest|largest|which payments|what did i buy)\b", text):
        args = {"sort": "amount" if re.search(r"biggest|largest", text) else "date"}
        if period:
            args["period"] = period
        if target:
            args.update(_target_filter(target))
        return "list_transactions", args
    if target or re.search(r"spen[dt]|how much|cost", text):
        args = {"period": period or "last_month"}
        if target:
            args.update(_target_filter(target))
        else:
            args["group_by"] = "category"
        if re.search(r"each month|per month|by month|monthly", text):
            args["group_by"] = "month"
        return "get_spending", args
    return "get_baskets", {}


def _target_filter(target: str) -> dict:
    resolved = engine.resolve_target(target)
    key = resolved["type"]
    return {key: target if key != "basket" else resolved["values"][0]}


def describe(name: str, r: dict) -> str:
    """One or two fixed sentences built from a tool result."""
    if "error" in r:
        return f"I could not work that out: {r['error']}"
    if name == "get_spending":
        what = " on " + ", ".join(str(v) for v in r["filters"].values()) if r["filters"] else ""
        text = f"You spent {eur(r['total'])}{what} in {r['period']['label']}, across {r['transactions']} payments."
        prev = r.get("previous_period")
        if prev and prev.get("change_pct") is not None:
            direction = "more" if prev["change"] > 0 else "less"
            text += f" That is {eur(abs(prev['change']))} {direction} than the period before."
        return text
    if name == "list_transactions":
        return (
            f"There are {r['matching_transactions']} matching payments in {r['period']['label']}, "
            f"{eur(r['total'])} in all. The list shows {r['shown']} of them."
        )
    if name == "get_payday_plan":
        parts = {row["key"]: row for row in r["split"]}
        text = (
            f"For your salary of {eur(r['payday']['expected_salary'])} on {r['payday']['date']}: "
            f"{eur(parts['essentials']['amount'])} for regular essentials, {eur(parts['unexpected']['amount'])} set aside for the unexpected, "
            f"{eur(parts['savings']['amount'])} to savings and {eur(parts['everyday']['amount'])} for everyday spending, "
            f"which is {eur(parts['everyday']['a_week'])} a week."
        )
        last = r.get("last_pay_period")
        if last:
            text += f" In your last pay period everyday spending was {eur(last['everyday'])}."
        return text
    if name == "get_balance_outlook":
        low = r["lowest_point"]
        h = r.get("heads_up")
        if not h:
            return (
                f"If the next weeks go like your usual ones, your balance stays above zero until {r['until']}. "
                f"Its lowest point would be {eur(low['balance'])} on {low['date']}."
            )
        text = (
            f"If the next weeks go like your usual ones, your balance goes below zero on {h['below_zero_from']} "
            f"and would be {eur(h['short_by'])} short at its lowest, on {h['deepest_point']['date']}."
        )
        bill = h.get("biggest_bill_before")
        if bill:
            text += f" Your {bill['what'].lower()} of about {eur(bill['amount'])} is expected around {bill['date']}."
        fix = h.get("fix")
        if fix:
            text += (
                f" Holding everyday spending to {eur(fix['a_week'])} a week instead of your usual {eur(fix['instead_of_a_week'])} "
                "would keep you above zero."
            )
        return text + " This is your usual pattern projected forward, not a forecast."
    if name == "get_baskets":
        e, u, d = r["baskets"]
        return (
            f"In {r['period']['label']} you spent {eur(r['spending'])}: {eur(e['total'])} on regular essentials, "
            f"{eur(u['total'])} on unexpected necessities and {eur(d['total'])} on everyday spending. "
            f"{r['small_everyday_purchases']['count']} everyday purchases were under EUR {r['small_everyday_purchases']['under_eur']}, "
            f"adding up to {eur(r['small_everyday_purchases']['total'])}."
        )
    if name == "get_cashflow":
        a = r["average"]
        return (
            f"Over {r['period']['label']} you averaged {eur(a['income'])} in and {eur(a['spending'])} out a month. "
            f"In {r['months_spent_more_than_earned']} of those months you spent more than you earned."
        )
    if name == "get_safe_to_spend":
        w = r["this_week"]
        return (
            f"You can safely spend {eur(w['safe_to_spend'])} on everyday things in the next {w['days_left']} days, "
            f"and {eur(r['safe_to_spend_until_payday'])} until payday on {r['pay_period']['next_payday']}. "
            f"That is {eur(r['safe_per_day'])} a day; you usually spend {eur(r['usual_everyday_per_day'])} a day."
        )
    if name == "check_affordability":
        lead = {"yes": "Yes.", "tight": "It fits, but it is tight.", "not_from_this_budget": "Not from this pay period's everyday budget.", "no": "Not right now."}
        text = f"{lead.get(r['fits'], '')} {r['why']} It would count as {r['item']['basket']}."
        treat = r.get("if_it_is_a_treat")
        if treat:
            text += f" If it is a treat rather than something you need: {treat['why']}"
        return text
    if name == "get_highlights":
        if not r["notices"]:
            return "Nothing unusual stands out in your money right now."
        return "What stands out right now: " + "; ".join(n["title"] for n in r["notices"]) + "."
    if name == "replay_year":
        s = r["shown"]
        days = s["days_below_zero"]
        text = (
            f"Replaying your last 12 months with one change, \"{s['title']}\", would have left {eur(s['kept_over_the_year'])} more "
            f"on your account: {eur(s['balance_today']['after'])} today instead of {eur(s['balance_today']['before'])}."
        )
        if days["before"]:
            text += f" Days below zero would have gone from {days['before']} to {days['after']}."
        return text + " This is your real history replayed, not a forecast."
    if name == "simulate_change":
        return (
            f"You spend about {eur(r['monthly_now'])} a month on {r['target']}. Changing that by {r['change_pct']:g}% "
            f"would free up {eur(r['monthly_saving'])} a month, or {eur(r['yearly_saving'])} a year."
        )
    if name == "get_spender_profile":
        t = r["traits"]
        return (
            f"You are a {r['spender_type']}. {r['summary']} You keep {t['share_of_income_left_over_pct']:g}% of your income, "
            f"and everyday spending is {r['basket_shares_pct']['everyday_spending']:g}% of what you spend. {r['tip']}"
        )
    if name == "compare_with_peers":
        parts = [
            f"{c['metric']}: you {c['you']:g}, typical {c['peer_median']:g} (higher than {c['higher_than_pct_of_peers']:g}% of peers)"
            for c in r["comparisons"][:3]
        ]
        return f"Compared with {r['compared_with']}: " + "; ".join(parts) + "."
    if name == "get_regular_payments":
        parts = [f"{i['what']} about {eur(i['monthly_amount'])} a month" for i in r["items"][:4]]
        return "Your regular money movements: " + ", ".join(parts) + "."
    if name == "get_mortgage_readiness":
        h = r["home"]
        first = r["what_would_matter_most"][0]["change"] if r["what_would_matter_most"] else "Nothing stands out to change."
        return (
            f"For a home of {eur(h['property_price'])} with {eur(h['own_money'])} of your own money, {r['readiness']}. "
            f"What would matter most: {first}. This is guidance, not a credit decision."
        )
    if name == "get_mortgage_application":
        if not r.get("has_application"):
            return "There is no mortgage application in your data."
        return f"Your application for a home of {eur(r['property_price'])} was {r['decision']} after {r['days']} days."
    if name == "explain_baskets":
        return "Every payment falls into one of three baskets: " + "; ".join(f"{b['name']} ({b['examples']})" for b in r["baskets"]) + "."
    return "Here is what I found."


def run(customer_id: str, message: str, note: str = "", has_image: bool = False) -> Iterator[dict]:
    started = time.time()
    try:
        name, args = route(message)
    except engine.EngineError:
        name, args = "get_baskets", {}
    if has_image and name != "check_affordability":
        # Reading a photo needs the vision model. Without it, ask for the price.
        yield {
            "type": "answer",
            "text": "I can only read photos when the AI model is connected. Type the price, for example "
            "\"Can I afford 89 euros?\", and I will check it against your budget.",
            "mode": "offline",
            "model": None,
            "note": note,
            "grounding": {"ok": True, "numbers_checked": 0, "unverified": [], "rewritten": False},
            "tools_used": [],
            "seconds": round(time.time() - started, 2),
        }
        return
    yield {"type": "tool_call", "name": name, "arguments": args}
    result = tools.call(customer_id, name, args)
    yield {"type": "tool_result", "name": name, "arguments": args, "result": result}
    yield {
        "type": "answer",
        "text": describe(name, result),
        "mode": "offline",
        "model": None,
        "note": note,
        "grounding": {"ok": True, "numbers_checked": 0, "unverified": [], "rewritten": False},
        "tools_used": [{"name": name, "arguments": args, "ok": "error" not in result}],
        "seconds": round(time.time() - started, 2),
    }
