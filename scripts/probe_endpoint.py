"""A few plain requests to a model endpoint, to tell a healthy model from a broken one.

    python scripts/probe_endpoint.py https://containers.verda.com/<deployment>/v1 [model-name]

The key is read from VERDA_INFERENCE_KEY in .env and is never printed.
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402,F401  (loads .env)

OFF = {"chat_template_kwargs": {"enable_thinking": False}}
TOOL = {
    "type": "function",
    "function": {
        "name": "get_spending",
        "description": "Total spending in a period, optionally by kind of place.",
        "parameters": {"type": "object", "properties": {"period": {"type": "string"}, "subcategory": {"type": "string"}}},
    },
}


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit(__doc__)
    base = argv[0].rstrip("/")
    model = argv[1] if len(argv) > 1 else "nemotron-3.5-super-vl"
    key = os.environ.get("VERDA_INFERENCE_KEY", "").strip()
    if not key:
        raise SystemExit("Set VERDA_INFERENCE_KEY in .env first.")
    headers = {"Authorization": f"Bearer {key}"}
    cases = [
        ("greedy", {"temperature": 0, "max_tokens": 24, "messages": [{"role": "user", "content": "What is the capital of Finland? One word."}]}),
        ("temperature 0.2", {"temperature": 0.2, "max_tokens": 40, "messages": [{"role": "user", "content": "Name three Finnish cities, comma separated."}]}),
        ("tool call", {"temperature": 0.2, "max_tokens": 200, "tool_choice": "auto", "tools": [TOOL], "messages": [{"role": "user", "content": "How much did I spend on taxis last month?"}]}),
    ]
    sane = 0
    for name, body in cases:
        started = time.time()
        try:
            reply = httpx.post(f"{base}/chat/completions", headers=headers, json={"model": model, **OFF, **body}, timeout=180)
        except httpx.HTTPError as exc:
            print(f"{name}: request failed: {type(exc).__name__}")
            continue
        took = time.time() - started
        if reply.status_code != 200:
            print(f"{name}: HTTP {reply.status_code} {reply.text[:160]!r} ({took:.1f} s)")
            continue
        message = reply.json()["choices"][0]["message"]
        text = (message.get("content") or "").replace("\n", " ")[:160]
        calls = [c["function"]["name"] + " " + c["function"]["arguments"][:80] for c in (message.get("tool_calls") or [])]
        print(f"{name}: answer {text!r} | tools {calls} | {took:.1f} s")
        if "Helsinki" in text or "Tampere" in text or "Turku" in text or "Espoo" in text or calls:
            sane += 1
    print(f"sane answers: {sane} of {len(cases)}")
    return 0 if sane == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
