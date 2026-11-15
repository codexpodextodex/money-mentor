"""Money Mentor deck, step 1: photograph the real app screens.

Drives the running demo app (http://127.0.0.1:8791) through the same postMessage contract the demo
page and the film use (web/README.md), waits for each screen to settle, scrolls it to the part the
slide talks about, and saves a screenshot at three times the phone's size to deck/screens/<name>.png,
with the screen's own text next to it (<name>.txt) so every figure on a slide can be checked.

    python deck/capture.py                 # all screens
    python deck/capture.py loan ask        # only some

Nothing is redrawn or edited: the deck puts these photographs inside the phone as they are.
The three chat answers are written by the model, so their wording differs a little between runs
(the figures do not: the engine computes them). As in video/capture.py, the capture asks again
until it gets a take in clean English. That is choosing a take; nothing is edited.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "screens"
BASE = "http://127.0.0.1:8791"
WHO = "CUST00086"      # the default demo customer, "Month-end stretcher"
SECOND = "CUST00874"   # "Experience seeker": the price-tag photo, exactly as in the film
SCALE = 3

FINNISH = r"Kyllä|\bEi\b|Luin|palkkapäiv|ylimäär|\bjuuri\b|\bnyt\b"
TAKES = {
    "ask": (r"€88\.90", FINNISH),
    "photo": (r"^\s*Can I afford this\?\s+Money trainer\s+I read", FINNISH),
    # The verdict, then the "when" in the model's words, then the card's own block. A take where the model
    # filed the jacket under Home & Tech is passed over: the card's small print would then talk about tech.
    "when": (r"^\s*Can I afford a €120 jacket\?\s+Money trainer\s+Not from this pay period's everyday budget\.[\s\S]*"
             r"Not from the next salary either\. With one habit changed, in about 2 months\.[\s\S]*"
             r"In about 2 months, with one habit changed", FINNISH + r"|Home & Tech"),
    # The draft card with both numbers checked and its button, under an answer that says nothing is paid yet.
    "bill": (r"^\s*Get this bill ready to pay\s+Money trainer\s+[\s\S]*Demo Sähkö Oy[\s\S]*"
             r"(?:[Nn]othing (?:is|has been|was) paid|not (?:yet )?(?:been )?paid|[Nn]o payment (?:has been|is|was) made)[\s\S]*"
             r"Payment draft[\s\S]*€84\.60[\s\S]*FI87 9999 9900 0123 44[\s\S]*20261 04577[\s\S]*Confirm the payment", FINNISH),
}

# name: language, route, ask message, selector that proves the data is there, customer,
#       (selector to scroll to, px to leave above it) or None for the top of the screen
SHOTS = {
    "home":       ("en", "home", None, '[data-tour="home-trainer"]', WHO, None),
    "account":    ("en", "account", None, ".screen.is-active", WHO, None),
    "trainer":    ("en", "trainer", None, '[data-tour="trainer-baskets"]', WHO, None),
    "notices":    ("en", "trainer", None, '[data-tour="trainer-baskets"]', WHO, ('[data-tour="trainer-notices"]', 14)),
    "baskets":    ("en", "trainer", None, '[data-tour="trainer-baskets"]', WHO, ('[data-tour="trainer-baskets"]', 14)),
    "plan":       ("en", "plan", None, '[data-tour="plan-outlook"]', WHO, None),
    "outlook":    ("en", "plan", None, '[data-tour="plan-outlook"]', WHO, ('[data-tour="plan-outlook"]', 14)),
    "replay":     ("en", "replay", None, '[data-tour="replay-levers"]', WHO, None),
    "ask":        ("en", None, {"text": "How much did I spend on fast food in the last 3 months?"}, ".trust", WHO, (".msg--bot .toolcard", 14)),
    "photo":      ("en", None, {"photo": "sample"}, ".readings", SECOND, (".msg--bot .toolcard", 14)),
    "when":       ("en", None, {"text": "Can I afford a €120 jacket?"}, ".whenfit", WHO, (".msg--bot .toolcard .bars", 0)),
    "bill":       ("en", None, {"text": "Get this bill ready to pay", "photo": "bill"}, ".pay__fields", WHO, (".msg--bot .toolcard", 8)),
    "loan":       ("en", "loan", None, '[data-tour="loan-pillars"]', WHO, None),
    "home-fi":    ("fi", "home", None, '[data-tour="home-trainer"]', WHO, None),
    "bank-sv":    ("sv", "bank", None, '[data-tour="bank-trainer"]', WHO, None),
    "trainer-fi": ("fi", "trainer", None, '[data-tour="trainer-baskets"]', WHO, None),
    "trainer-sv": ("sv", "trainer", None, '[data-tour="trainer-baskets"]', WHO, None),
}

# Scroll the screen's own scroll container, at once, so that `selector` sits `gap` px under its top edge.
SCROLL = r"""
([selector, gap]) => {
  const root = document.querySelector('.screen.is-active') || document.body;
  const el = root.querySelector(selector) || document.querySelector(selector);
  if (!el) return 'missing ' + selector;
  let box = el.parentElement;
  while (box && !(/(auto|scroll)/.test(getComputedStyle(box).overflowY) && box.scrollHeight > box.clientHeight + 2)) box = box.parentElement;
  if (!box) return 'nothing scrolls';
  const top = box.scrollTop + el.getBoundingClientRect().top - box.getBoundingClientRect().top - gap;
  box.scrollTo({ top, behavior: 'instant' });
  return 'ok';
}
"""

FACTS = r"""
() => {
  const screen = document.querySelector('.screen.is-active') || document.body;
  const demo = [...document.querySelectorAll('*')].filter((el) => !el.children.length && /^demo$/i.test((el.textContent || '').trim()))
    .some((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.top >= 0 && r.bottom <= innerHeight; });
  const families = new Set();
  document.fonts.forEach((face) => { if (face.status === 'loaded') families.add(face.family.replace(/["']/g, '')); });
  return { text: screen.innerText, demo, families: [...families], lang: document.documentElement.lang };
}
"""


async def take(browser, name: str) -> bool:
    lang, route, ask, proof, who, scroll = SHOTS[name]
    ctx = await browser.new_context(viewport={"width": 402, "height": 874}, device_scale_factor=SCALE, locale="en-GB")
    page = await ctx.new_page()
    url = f"{BASE}/app?embed=1&lang={lang}&who={who}"
    await page.goto(url)
    await page.wait_for_timeout(2300)  # the launch screen plays, then leaves
    post = "(m) => window.postMessage(Object.assign({ source: 'mm' }, m), location.origin)"
    started = time.time()
    if route:
        await page.evaluate(post, {"type": "goto", "route": route, "highlight": None})
    if ask:
        await page.evaluate(post, {"type": "ask", **ask})
    await page.wait_for_selector(proof, timeout=60000)
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2600 if ask else 1800)  # charts, bars and ticks finish their own entrance
    await page.evaluate("() => document.fonts.ready")
    if scroll:
        result = await page.evaluate(SCROLL, list(scroll))
        if result != "ok":
            raise SystemExit(f"{name}: could not scroll ({result})")
        await page.wait_for_timeout(500)
    facts = await page.evaluate(FACTS)
    if name in TAKES:
        must, must_not = TAKES[name]
        answer = facts["text"].split("New chat")[0]  # the conversation, without the suggestion chips under it
        if not re.search(must, answer) or re.search(must_not, answer):
            await ctx.close()
            return False
    if not facts["demo"]:
        raise SystemExit(f"{name}: the app's own Demo mark is not on screen, not saved")
    if "S Bonus UX" not in facts["families"]:
        raise SystemExit(f"{name}: the app is not showing the bank's typeface (web/brand/ missing?), not saved")
    (OUT / f"{name}.txt").write_text(facts["text"], encoding="utf-8")
    await page.screenshot(path=str(OUT / f"{name}.png"))
    meta = {"name": name, "url": url, "route": route, "ask": ask, "customer": who, "language": lang,
            "scrolled_to": scroll[0] if scroll else None, "captured": time.strftime("%Y-%m-%d %H:%M:%S"), "scale": SCALE}
    (OUT / f"{name}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"{name:12s} {time.time() - started:4.1f} s")
    await ctx.close()
    return True


async def shoot(browser, name: str) -> None:
    for attempt in range(1, 11):
        if await take(browser, name):
            return
        print(f"{name:12s} take {attempt} did not read well, asking again")
    raise SystemExit(f"No usable take of '{name}' in ten tries")


def figures() -> None:
    """The engine's own JSON for the demo customers, saved next to the screens."""
    out = {}
    for key in ("overview", "safe-to-spend", "baskets", "replay", "notices", "outlook"):
        with urllib.request.urlopen(f"{BASE}/api/customers/{WHO}/{key}") as response:
            out[key] = json.load(response)
    with urllib.request.urlopen(f"{BASE}/api/health") as response:
        health = json.load(response)
    out["health"] = {k: health[k] for k in ("ok", "today", "model", "hosts", "tools") if k in health}
    (OUT / "figures.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


async def main(names: list[str]) -> None:
    OUT.mkdir(exist_ok=True)
    try:
        urllib.request.urlopen(f"{BASE}/api/health", timeout=5)
    except OSError:
        raise SystemExit(f"The demo app is not answering at {BASE}. Start it (python run.py) and run this again.")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name in names:
            await shoot(browser, name)
        await browser.close()
    figures()


if __name__ == "__main__":
    asyncio.run(main([a for a in sys.argv[1:] if a in SHOTS] or list(SHOTS)))
