"""Measure how well each way of answering does on questions with known answers.

For a sample of customers, a fixed set of questions (English, Finnish and
Swedish) is asked. The right tool, the right arguments and the right number
are known in advance, because the engine computes them directly.

Systems compared:
    router            the keyword router, no language model
    model-minimal     the model with a bare prompt and no number check
    model-coach       the model with the coach prompt, no number check
    model-checked     the coach prompt plus the number check with one rewrite (what the app runs)

Usage:
    python scripts/evaluate.py                    # router only, if no model is configured
    python scripts/evaluate.py --customers 5      # more customers
    python scripts/evaluate.py --systems router model-checked

Writes eval/results.json and eval/results.md.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import agent, config, db, engine, grounding, insights, mortgage, offline  # noqa: E402

SYSTEMS = ["router", "model-minimal", "model-coach", "model-checked"]


def cases_for(cid: str) -> list[dict]:
    """Questions for one customer, each with the expected tool, arguments and numbers."""
    taxis = engine.spending(cid, "last_month", subcategory="Taxis")
    groceries = engine.spending(cid, "last_month", category="Groceries")
    restaurants_year = engine.spending(cid, "this_year", category="Restaurants")
    safe = engine.safe_to_spend(cid)
    dining = engine.what_if(cid, "Restaurants", -20)
    fun = engine.what_if(cid, "Entertainment", -50)
    profile = insights.spender_profile(cid)
    three = engine.basket_summary(cid, "last_3_months")
    peers = insights.benchmark(cid, "Restaurants")["comparisons"][0]
    home = mortgage.readiness(cid, property_price=250000)
    flow = engine.cashflow(cid, 6)
    biggest = engine.transactions(cid, "last_month", sort="amount", limit=1)
    biggest_amount = biggest["transactions"][0]["amount"] if biggest["transactions"] else 0.0
    basket_totals = [b["total"] for b in three["baskets"]] + [b.get("monthly_average", 0) for b in three["baskets"]]

    return [
        {
            "id": "taxis_last_month",
            "lang": "en",
            "question": "How much did I spend on taxis last month?",
            "tools": ["get_spending"],
            "args": {"period": "last_month", "target": "Taxis"},
            "numbers": [taxis["total"]],
        },
        {
            "id": "groceries_last_month_fi",
            "lang": "fi",
            "question": "Paljonko käytin ruokaostoksiin viime kuussa?",
            "tools": ["get_spending"],
            "args": {"period": "last_month", "target": "Groceries"},
            "numbers": [groceries["total"]],
        },
        {
            "id": "restaurants_this_year_sv",
            "lang": "sv",
            "question": "Hur mycket har jag lagt på restauranger i år?",
            "tools": ["get_spending"],
            "args": {"period": "this_year", "target": "Restaurants"},
            "numbers": [restaurants_year["total"]],
        },
        {
            "id": "safe_this_week",
            "lang": "en",
            "question": "What is safe for me to spend this week?",
            "tools": ["get_safe_to_spend"],
            "args": {},
            "numbers": [safe["this_week"]["safe_to_spend"], safe["safe_to_spend_until_payday"], safe["safe_per_day"]],
        },
        {
            "id": "safe_this_week_fi",
            "lang": "fi",
            "question": "Paljonko voin turvallisesti käyttää rahaa tällä viikolla?",
            "tools": ["get_safe_to_spend"],
            "args": {},
            "numbers": [safe["this_week"]["safe_to_spend"], safe["safe_to_spend_until_payday"], safe["safe_per_day"]],
        },
        {
            "id": "dining_minus_20",
            "lang": "en",
            "question": "How much could I save if I reduced dining out by 20%?",
            "tools": ["simulate_change"],
            "args": {"target": "Restaurants", "change_pct": -20},
            "numbers": [dining["monthly_saving"], dining["yearly_saving"]],
        },
        {
            "id": "entertainment_halved",
            "lang": "en",
            "question": "What if I halved what I spend on entertainment?",
            "tools": ["simulate_change"],
            "args": {"target": "Entertainment", "change_pct": -50},
            "numbers": [fun["monthly_saving"], fun["yearly_saving"]],
        },
        {
            "id": "spender_type",
            "lang": "en",
            "question": "What kind of spender am I?",
            "tools": ["get_spender_profile"],
            "args": {},
            "text": [profile["spender_type"]],
        },
        {
            "id": "where_did_money_go",
            "lang": "en",
            "question": "Where did my money really go over the last three months?",
            "tools": ["get_baskets", "get_spending"],
            "args": {},
            "numbers": basket_totals + [three["spending"]],
        },
        {
            "id": "peers_restaurants",
            "lang": "en",
            "question": "Do I spend more on restaurants than other people my age?",
            "tools": ["compare_with_peers"],
            "args": {"target": "Restaurants"},
            "numbers": [peers["peer_median"], peers["you"], peers["higher_than_pct_of_peers"]],
        },
        {
            "id": "mortgage_250k",
            "lang": "en",
            "question": "Could I get a mortgage for a 250,000 euro home?",
            "tools": ["get_mortgage_readiness"],
            "args": {"property_price": 250000},
            "numbers": [
                home["you"]["largest_loan_your_income_supports"],
                home["home"]["loan"],
                home["home"]["own_money"],
                home["you"]["price_range_with_this_own_money"],
            ],
        },
        {
            "id": "biggest_payment",
            "lang": "en",
            "question": "What was my single biggest payment last month?",
            "tools": ["list_transactions", "get_spending", "run_sql"],
            "args": {},
            "numbers": [biggest_amount],
        },
        {
            "id": "more_than_earned",
            "lang": "en",
            "question": "On average over the last six months, how much came in and how much went out each month?",
            "tools": ["get_cashflow", "get_baskets"],
            "args": {},
            "numbers": [flow["average"]["income"], flow["average"]["spending"]],
        },
    ]


# When the right answer is zero, the coach says so in words ("You spent nothing on taxis").
_ZERO_IN_WORDS = (
    "nothing", "no spending", "did not spend", "didn't spend", "not spent", "would not change",
    "et käyttänyt", "ei mitään", "ei lainkaan", "ei ollut", "ei muuttaisi",
    "ingenting", "inget", "inte lagt", "inte spenderat", "inga ",
)


def _number_in(text: str, wanted: float) -> bool:
    if any(abs(abs(v) - abs(wanted)) <= max(0.51, 0.005 * abs(wanted)) for _, v in grounding.numbers_in_text(text)):
        return True
    return abs(wanted) < 0.005 and any(phrase in text.lower() for phrase in _ZERO_IN_WORDS)


def _args_match(expected: dict, calls: list[dict]) -> bool:
    """True if one of the calls carries the expected arguments (after normalising names)."""
    if not expected:
        return True
    for call in calls:
        got = call["arguments"]
        ok = True
        for key, want in expected.items():
            if key == "target":
                raw = got.get("target") or got.get("subcategory") or got.get("category") or got.get("basket")
                try:
                    ok &= bool(raw) and engine.resolve_target(str(raw))["label"] == engine.resolve_target(want)["label"]
                except engine.EngineError:
                    ok = False
            elif isinstance(want, (int, float)):
                try:
                    ok &= abs(float(got.get(key)) - float(want)) < 0.01
                except (TypeError, ValueError):
                    ok = False
            else:
                ok &= str(got.get(key, "")).lower().replace("-", "_") == str(want).lower()
        if ok:
            return True
    return False


def ask(system: str, cid: str, question: str) -> dict:
    started = time.time()
    if system == "router":
        events = list(offline.run(cid, question))
    else:
        style = "minimal" if system == "model-minimal" else "coach"
        events = list(agent.run(cid, question, prompt_style=style, verify=(system == "model-checked")))
    answer = next((e for e in reversed(events) if e["type"] == "answer"), {"text": "", "mode": "none"})
    calls = [e for e in events if e["type"] == "tool_call"]
    results = [e["result"] for e in events if e["type"] == "tool_result"]
    return {
        "text": answer.get("text", ""),
        "mode": answer.get("mode"),
        "calls": [{"name": c["name"], "arguments": c["arguments"]} for c in calls],
        "grounded": grounding.check(answer.get("text", ""), results, question)["ok"],
        "rewritten": bool(answer.get("grounding", {}).get("rewritten")),
        "seconds": round(time.time() - started, 2),
    }


def score(case: dict, got: dict) -> dict:
    names = [c["name"] for c in got["calls"]]
    right_tool = any(n in case["tools"] for n in names)
    right_args = right_tool and _args_match(case["args"], [c for c in got["calls"] if c["name"] in case["tools"]])
    if "text" in case:
        right_answer = any(t.lower() in got["text"].lower() for t in case["text"])
    else:
        right_answer = any(_number_in(got["text"], n) for n in case["numbers"])
    return {"tool": right_tool, "args": right_args, "answer": right_answer, "grounded": got["grounded"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Money Mentor's answers against known numbers.")
    parser.add_argument("--customers", type=int, default=3, help="how many held-out customers to test")
    parser.add_argument("--systems", nargs="+", choices=SYSTEMS, help="which systems to run")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds to wait between model questions (rate limits)")
    args = parser.parse_args()

    db.init()
    systems = args.systems or (SYSTEMS if config.llm_configured() else ["router"])
    if not config.llm_configured():
        skipped = [s for s in systems if s != "router"]
        if skipped:
            print("No model configured (set LLM_API_KEY and LLM_MODEL): skipping", ", ".join(skipped))
        systems = [s for s in systems if s == "router"]

    # Held-out customers: a fixed random sample, none of them a demo persona.
    demo = {p["customer_id"] for p in insights.personas()}
    sample = [
        r["customer_id"]
        for r in db.rows("SELECT customer_id FROM cust_features USING SAMPLE 40 ROWS (reservoir, 2026) ORDER BY 1")
        if r["customer_id"] not in demo
    ][: args.customers]

    rows = []
    for system in systems:
        for cid in sample:
            for case in cases_for(cid):
                got = ask(system, cid, case["question"])
                rows.append({"system": system, "customer_id": cid, "case": case["id"], "lang": case["lang"], **score(case, got), **got})
                mark = "".join("Y" if rows[-1][k] else "-" for k in ("tool", "args", "answer", "grounded"))
                print(f"{system:<14} {cid} {case['id']:<26} {mark} {got['seconds']:>5.1f}s")
                if system != "router" and args.pause:
                    time.sleep(args.pause)

    summary = []
    for system in systems:
        mine = [r for r in rows if r["system"] == system]
        n = len(mine)
        summary.append(
            {
                "system": system,
                "questions": n,
                "right_tool_pct": round(100 * sum(r["tool"] for r in mine) / n, 1),
                "right_arguments_pct": round(100 * sum(r["args"] for r in mine) / n, 1),
                "right_number_in_answer_pct": round(100 * sum(r["answer"] for r in mine) / n, 1),
                "every_number_traceable_pct": round(100 * sum(r["grounded"] for r in mine) / n, 1),
                "non_english_right_pct": round(
                    100 * sum(r["answer"] for r in mine if r["lang"] != "en") / max(1, sum(1 for r in mine if r["lang"] != "en")), 1
                ),
                "answers_rewritten": sum(r["rewritten"] for r in mine),
                "fell_back_to_router": sum(1 for r in mine if system != "router" and r["mode"] == "offline"),
                "median_seconds": sorted(r["seconds"] for r in mine)[n // 2],
            }
        )

    out = ROOT / "eval"
    out.mkdir(exist_ok=True)
    meta = {"model": config.LLM_MODEL or None, "base_url": config.LLM_BASE_URL if config.llm_configured() else None, "customers": sample, "as_of": db.today().isoformat()}
    (out / "results.json").write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")

    header = "| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |"
    lines = [header, "|---|---|---|---|---|---|---|---|"]
    for s in summary:
        lines.append(
            f"| {s['system']} | {s['questions']} | {s['right_tool_pct']}% | {s['right_arguments_pct']}% | "
            f"{s['right_number_in_answer_pct']}% | {s['every_number_traceable_pct']}% | {s['non_english_right_pct']}% | {s['median_seconds']} s |"
        )
    text = (
        "# Evaluation\n\n"
        f"Model: `{meta['model']}`. Held-out customers: {', '.join(sample)}. Data as of {meta['as_of']}.\n\n"
        + "\n".join(lines)
        + "\n\nProduced by `python scripts/evaluate.py`. Expected tools, arguments and numbers come from calling the engine directly.\n"
    )
    (out / "results.md").write_text(text, encoding="utf-8")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
