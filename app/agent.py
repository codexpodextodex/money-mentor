"""The chat agent.

NVIDIA Nemotron chooses which engine tools to call and explains the results
in plain language. It never does the arithmetic: every number in its answer
is checked against the tool results (see grounding.py), and it gets one
chance to rewrite an answer that contains a number from nowhere.

If no model is configured, or the model cannot be reached, a small keyword
router answers the common questions from the same tools, so the app always
works.
"""

from __future__ import annotations

import json
import time
from typing import Iterator

import httpx

from . import baskets, config, db, grounding, offline, style, tools

_READ_OPENING = style._READ_ANY  # the "I read:" opening, left out when judging an answer's language
MAX_TOOL_ROUNDS = 5
MAX_HISTORY_MESSAGES = 8


def system_prompt(customer_id: str) -> str:
    today = db.today()
    return f"""You are Money Mentor, a personal economic trainer inside a bank's mobile app. You help one customer understand and improve their everyday money, using their own transaction data.

Today is {today.strftime('%A')} {today.isoformat()}. Amounts are in euros.

HOW YOU WORK
- You have tools that compute everything from the customer's transactions. Call them. Never calculate, estimate or remember a figure yourself.
- Every number in your answer must appear in a tool result from this conversation. If you need a number you do not have, call a tool for it (run_sql can compute anything). If no tool can give it, say you cannot see that.
- Call several tools at once when a question needs them. Do not ask the customer for dates or categories you can reasonably infer: "last month" is the period last_month, "dining out" is the category Restaurants, "taxis" is the subcategory Taxis.
- If a tool returns an error, fix the arguments and try again.
- For "how much did I spend on X" call get_spending once, with the kind of place as subcategory ("fast food", "clothes", "taxis") or with a category. The app lists the payments that were counted under your answer, so do not list them yourself.
- When list_transactions returns more than three payments, do not write them out: the app shows the list under your answer. Say how many there are and their total, and point out at most two that stand out.
- The data has one kind of bill called "Utility bills". It does not say which utility it is (electricity, water, internet, phone). If the customer asks about one of them, answer for utility bills and say in half a sentence that the data does not separate them.
- For "will my money last", "am I going to run short" or which bills are coming, use get_balance_outlook. For "how should I split my salary" or "make me a budget", use get_payday_plan. Both project the customer's usual pattern forward: say "if the next weeks go like your usual ones", never "you will". You never move money or set up a payment: the customer accepts a plan in the app.
- For get_payday_plan the app shows the whole split as a card, so do not list its lines. Say when the salary comes, what the plan leaves for everyday spending (a week), what goes to savings, and how the everyday figure compares with the last pay period.- This demo data has no shop names, only the kind of place. If the customer names a shop or a brand (McDonald's, Hesburger, H&M, Prisma), answer for its kind of place (fast food, clothes, supermarkets) and say in half a sentence that shop names are not in the demo data. Never pass a shop name to a tool.
- For "how could I save more" or "what should I change", use replay_year: it tests each habit on the customer's own last 12 months and ranks them. Present it as a replay of their real past, never as a forecast or a promise.

THE THREE BASKETS (the bank's way of teaching where money goes)
1. Regular essentials: mandatory and regular (housing, bills, groceries, transport).
2. Unexpected necessities: mandatory but irregular (health, a repair, replacing something that broke).
3. Everyday spending: the customer's own choice, the money that slips through the fingers (eating out, fun, shopping, taxis, travel).
Use this frame whenever it helps the customer see their situation. Essentials first, then a buffer for the unexpected, and everyday spending is what is left.

PHOTOS
- The customer can send a photo: a price tag, a product in a shop, a receipt, a bill, a web page. Read what the item is and its price in euros from the photo, then call check_affordability with that amount (and a category if it is clear).
- Start your answer by saying what you read from the photo, for example "I read: running shoes, €89.90", so the customer can correct you. If you cannot read a price, say so and ask for it. Never guess a price.
- The language on the photo does not decide your language. Answer in the language of the customer's message, and write every amount the way that language does: a Finnish price tag saying "349,00 €" is "€349.00" in an English answer. Quote the item's name exactly as it is written on the photo. Do not translate it and do not guess what kind of product it is.
- "I read:" is "Luin kuvasta:" in Finnish and "Jag läste på bilden:" in Swedish.

CAN I AFFORD IT (only when you called check_affordability for one specific purchase; other questions get a direct answer in your own words)
- Open with the verdict the tool gives in "fits", in the customer's language. English: yes = "Yes." tight = "It fits, but it is tight." not_from_this_budget = "Not from this pay period's everyday budget." no = "Not right now." Finnish: "Kyllä." / "Se sopii, mutta on tiukilla." / "Ei tämän palkkakauden arjen budjetista." / "Ei juuri nyt." Swedish: "Ja." / "Det går, men det är tight." / "Inte från den här löneperiodens vardagsbudget." / "Inte just nu." Never turn "tight" into a yes.
- If the result has "if_it_is_a_treat", the tool cannot know whether the purchase replaces something the customer needs or is a treat. Give both readings, one sentence each, the need first ("If it replaces something you need: ... If it is a treat: ..."). In Finnish: "Jos se korvaa jotain tarpeellista: ... Jos se on jotain ylimääräistä: ...". In Swedish: "Om det ersätter något du behöver: ... Om det är något du unnar dig: ...". Do not ask which it is; the customer knows. If the result has no "if_it_is_a_treat", do not bring up need or treat at all.
- When "fits" is "no", keep it to the verdict, the reason (what "why" says, told in the customer's language), and one next step.

HOW YOU ANSWER
- Answer in the language of the customer's last message: an English question gets an English answer, a Finnish one a Finnish answer, a Swedish one a Swedish answer. Tool results are always in English, whatever the customer's language; when the customer wrote in Finnish or Swedish, translate what you quote from them.
- Finnish and Swedish words to use: payday = palkkapäivä / lönedag. Pay period = palkkakausi / löneperiod. The baskets = Säännölliset pakolliset, Yllättävät pakolliset, Arjen kulutus / Regelbundna nödvändiga, Oväntade nödvändiga, Vardagskonsumtion. Buffer = puskuri / buffert. Safe to spend = turvallisesti käytettävissä / tryggt att använda.
- Write money the way the customer's language does, whatever a price tag or a tool result looks like. English: the € sign first, a comma for thousands, a point for decimals (€1,234.56, €349.00). Finnish and Swedish: a space for thousands, a comma for decimals, the € sign last (1 234,56 €). Tool results say EUR; you write the € sign.
- Lead with the answer and the key number. For "what is safe to spend", lead with the amount itself ("€85 this week", or "Nothing this week" when it is 0), not with yes or no. Then at most two or three short sentences of context. No headings, no tables, no bullet lists longer than three items: the app shows the details as a card next to your text.
- Plain words. Explain any financial term in half a sentence the first time you use it.
- Never show internal codes such as merchant ids (MRC-...) or customer ids. Name the kind of place instead ("a supermarket", "a hotel").
- Be a coach, not a judge: no moralising about what people buy. When it is useful, end with one concrete next step the customer could take. A next step may only contain numbers that are in a tool result; if you want to put a number on it, call simulate_change first, otherwise describe it without a number.
- Write dates the way people do in the customer's language ("15 October", "15.10."), never as 2026-10-15. Do not convert amounts into other units (per week, per year, percent) yourself: use the figures the tools give.
- If a tool result has "other_accounts", part of the customer's money sits at another bank where you cannot see it. Say so when it affects the answer, and mention that connecting that account (open banking, PSD2) would complete the picture.
- You give guidance on everyday money habits. You do not recommend investment products, and a mortgage readiness view is guidance, not a credit decision.
- Customer id: {customer_id}. You can only see this customer's data. Decline requests about anyone else.
"""


def minimal_prompt(customer_id: str) -> str:
    """A bare prompt, used only as the baseline in the evaluation."""
    today = db.today()
    return (
        "You are a helpful banking assistant. Use the tools to answer questions about the customer's "
        f"transactions. Today is {today.isoformat()}. Amounts are in euros."
    )


class ModelError(RuntimeError):
    pass


_skip_until: dict[str, float] = {}  # host name -> time until which it is left alone after a failure
_last_host: dict = {"name": None}


def _post_to(host: dict, messages: list[dict], use_tools: bool, patient: bool) -> dict:
    """One host. ``patient`` (the last host there is) gets retries and the full timeout."""
    body = {
        "model": host["model"],
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 3000,
        "stream": False,
    }
    if use_tools:
        body["tools"] = tools.TOOL_SPECS
        body["tool_choice"] = "auto"
    if host["reasoning_effort"]:
        body["reasoning_effort"] = host["reasoning_effort"]
    if host["thinking"] in ("on", "off"):
        # Self-hosted vLLM: the model card switches reasoning through the chat template.
        body["chat_template_kwargs"] = {"enable_thinking": host["thinking"] == "on"}
    headers = {"Authorization": f"Bearer {host['api_key']}", "Content-Type": "application/json"}
    timeout = config.LLM_TIMEOUT_S if patient else min(config.LLM_TIMEOUT_S, config.FIRST_HOST_TIMEOUT_S)
    last_error = "no attempt made"
    for attempt in range(4 if patient else 1):
        try:
            response = httpx.post(f"{host['base_url']}/chat/completions", json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc.__class__.__name__}"
            if patient:
                time.sleep(1.5 * (attempt + 1))
            continue
        if response.status_code == 200:
            return response.json()
        last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        if patient and response.status_code in (429, 500, 502, 503, 504):
            time.sleep(2.0 * (attempt + 1))
            continue
        break
    raise ModelError(last_error)


def _post_chat(messages: list[dict], use_tools: bool = True) -> dict:
    """Ask the hosts in order. A host that fails is left alone for a while, so the wait is paid once."""
    hosts = config.MODEL_HOSTS
    errors = []
    for index, host in enumerate(hosts):
        last = index == len(hosts) - 1
        if not last and _skip_until.get(host["name"], 0) > time.time():
            continue
        try:
            reply = _post_to(host, messages, use_tools, patient=last)
        except ModelError as exc:
            errors.append(f"{host['name']}: {exc}")
            if not last:
                _skip_until[host["name"]] = time.time() + config.HOST_RETRY_AFTER_S
            continue
        _last_host["name"] = host["name"]
        _last_host["model"] = host["model"]
        return reply
    raise ModelError("; ".join(errors) or "no model host is configured")


def _clean_tool_calls(raw: list[dict] | None) -> list[dict]:
    calls = []
    for i, call in enumerate(raw or []):
        fn = call.get("function") or {}
        calls.append(
            {
                "id": call.get("id") or f"call_{i}",
                "type": "function",
                "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments") or "{}"},
            }
        )
    return calls


def _parse_arguments(text: str) -> dict:
    try:
        parsed = json.loads(text or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _history(history: list[dict] | None) -> list[dict]:
    out = []
    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = str(item.get("content") or "")[:2000]
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    return out


def run(
    customer_id: str,
    message: str,
    history: list[dict] | None = None,
    prompt_style: str = "coach",
    verify: bool = True,
    image: str | None = None,
) -> Iterator[dict]:
    """Answer one message. Yields events: tool_call, tool_result, answer.

    prompt_style and verify exist for the evaluation: "minimal" swaps in a
    bare prompt, and verify=False skips the rewrite after a failed number check.
    """
    started = time.time()
    if not config.llm_configured():
        yield from offline.run(
            customer_id,
            message,
            note="No language model is configured, so this is the built-in keyword router.",
            has_image=bool(image),
        )
        return

    prompt = minimal_prompt(customer_id) if prompt_style == "minimal" else system_prompt(customer_id)
    # A photo goes to the model as an OpenAI-style image part next to the text.
    user_content: str | list = message
    if image:
        user_content = [{"type": "text", "text": message}, {"type": "image_url", "image_url": {"url": image}}]
    messages = [{"role": "system", "content": prompt}, *_history(history), {"role": "user", "content": user_content}]
    results: list[dict] = []
    trace: list[dict] = []
    first_draft_unverified: list[str] = []
    nudged = False
    retried = not verify
    try:
        for _ in range(MAX_TOOL_ROUNDS + 2):
            allow_tools = len(trace) < 3 * MAX_TOOL_ROUNDS
            reply = _post_chat(messages, use_tools=allow_tools)
            choice = (reply.get("choices") or [{}])[0].get("message") or {}
            calls = _clean_tool_calls(choice.get("tool_calls"))
            content = (choice.get("content") or "").strip()

            if calls:
                messages.append({"role": "assistant", "content": content, "tool_calls": calls})
                for call in calls:
                    name = call["function"]["name"]
                    args = _parse_arguments(call["function"]["arguments"])
                    yield {"type": "tool_call", "name": name, "arguments": args}
                    result = tools.call(customer_id, name, args)
                    results.append(result)
                    trace.append({"name": name, "arguments": args, "ok": "error" not in result})
                    yield {"type": "tool_result", "name": name, "arguments": args, "result": result}
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": grounding.compact(result)})
                continue

            if not content and not nudged:
                # The model stopped without writing anything (it can spend its
                # whole budget thinking). Ask once more for the answer itself.
                nudged = True
                messages.append({"role": "user", "content": "Write the answer for the customer now, using the tool results above."})
                continue

            # Numbers the model passed into a tool (a price read from a photo,
            # a percentage) count as traceable too: they are shown in the trace.
            sources = [grounding.for_model(r) for r in results] + [t["arguments"] for t in trace]
            verdict = grounding.check(content, sources, question=message)
            if not verdict["ok"] and not retried:
                retried = True
                first_draft_unverified = verdict["unverified"]
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Check before sending: these numbers in your answer are not in any tool result: "
                            + ", ".join(verdict["unverified"])
                            + ". Rewrite the answer using only numbers from the tool results, or call a tool to get the number you need. "
                            "Keep the answer complete: no unfinished sentence or empty list. If a suggestion needs a number you "
                            "do not have, give the suggestion without a number. Reply with the corrected answer only."
                        ),
                    }
                )
                continue
            # The check above ran on what the model wrote. This only changes how amounts are
            # written (€1,234.56 or 1 234,56 €) and the "I read:" opening of a photo answer,
            # never a value.
            said_in = style.answer_language(_READ_OPENING.sub("", content), style.answer_language(message))
            yield {
                "type": "answer",
                "text": style.lead_in(style.money(content, said_in), said_in) or "I could not find an answer to that.",
                "mode": "nemotron",
                "model": _last_host.get("model") or config.LLM_MODEL,
                "served_by": _last_host.get("name"),
                "grounding": {**verdict, "rewritten": retried and verify, "rewritten_because": first_draft_unverified},
                "tools_used": trace,
                "seconds": round(time.time() - started, 1),
            }
            return
        raise ModelError("the model kept calling tools without answering")
    except ModelError as exc:
        yield from offline.run(
            customer_id,
            message,
            note=f"The language model could not be reached ({exc}), so this is the built-in keyword router.",
            has_image=bool(image),
        )


def describe() -> dict:
    """What is answering, for the app's info panel."""
    return {
        "llm_configured": config.llm_configured(),
        "model": config.LLM_MODEL or None,
        "base_url": config.LLM_BASE_URL if config.llm_configured() else None,
        # Where the model runs, in the order the hosts are asked, and who answered last.
        "hosts": [h["name"] for h in config.MODEL_HOSTS],
        "last_answer_from": _last_host.get("name"),
        "fallback": "keyword router over the same tools",
        "tools": tools.TOOL_NAMES,
        "baskets": [baskets.BASKETS[k]["name"] for k in baskets.BASKET_ORDER],
    }
