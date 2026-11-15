"""How reliably is a bill read from a photo, and does a misread ever get through?

Renders made-up bills (different layouts, languages, typefaces, tilt, blur and JPEG quality), sends each
one through the app exactly as a customer would ("get this bill ready to pay" with the photo), and
compares what the model passed to the engine with what was printed on the bill.

    python scripts/bill_reading_test.py render 1000          # make the bills (system Python with Playwright)
    python scripts/bill_reading_test.py run 0 8              # shard 0 of 8; start one process per shard
    python scripts/bill_reading_test.py report               # eval/bill-reading.md and .json

Every company, customer and account is invented. The account numbers use bank code 99, which no
Finnish bank has, with a correct check number. The bills are rendered, not photographed.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import random
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
# BILL_SET names a set of bills. The unnamed set is the one the checks were tuned on; a named set has
# other bills (another seed), so a result on it is a result on bills nobody had looked at.
SET = os.environ.get("BILL_SET", "").strip()
WORK = ROOT / "eval" / ("bills" + (f"-{SET}" if SET else ""))  # images and raw results: not in git
SEED = 20261115 + sum(ord(ch) * (i + 1) for i, ch in enumerate(SET))


# ------------------------------------------------------------------ the bills ---


def iban_fi(bban: str) -> str:
    return f"FI{98 - int(bban + '151800') % 97:02d}{bban}"


def fi_reference(base: str) -> str:
    total = sum(int(d) * (7, 3, 1)[i % 3] for i, d in enumerate(reversed(base)))
    return base + str((10 - total % 10) % 10)


def rf_reference(base: str) -> str:
    digits = "".join(str(int(ch, 36)) for ch in base + "RF00")
    return f"RF{98 - int(digits) % 97:02d}{base}"


def grouped(text: str, size: int = 4, from_right: bool = False) -> str:
    if from_right:
        text = text[::-1]
    out = " ".join(text[i : i + size] for i in range(0, len(text), size))
    return out[::-1] if from_right else out


WORDS = {
    "fi": {
        "title": "LASKU", "payee": "Saaja", "iban": "Saajan tilinumero (IBAN)", "ref": "Viitenumero", "due": "Eräpäivä", "sum": "Maksettava yhteensä",
        "pay": "MAKSUTIEDOT", "customer": "Asiakas", "number": "Laskun numero", "dated": "Laskun päivämäärä", "note": "Esimerkkilasku demoa varten. Yritys, asiakas ja tili ovat keksittyjä.",
        "kinds": ["Sähkö", "Vesi", "Lämpö", "Netti", "Puhelin", "Vakuutus", "Kuntosali", "Isännöinti", "Jätehuolto", "Hammashoito"], "forms": ["Oy", "Oyj", "Osk"],
        "lines": ["Perusmaksu", "Käyttömaksu", "Palvelumaksu"], "ask": "Maksa tämä lasku",
    },
    "sv": {
        "title": "FAKTURA", "payee": "Mottagare", "iban": "Mottagarens kontonummer (IBAN)", "ref": "Referensnummer", "due": "Förfallodag", "sum": "Att betala",
        "pay": "BETALNINGSUPPGIFTER", "customer": "Kund", "number": "Fakturanummer", "dated": "Fakturadatum", "note": "Exempelfaktura för en demo. Företaget, kunden och kontot är påhittade.",
        "kinds": ["El", "Vatten", "Värme", "Bredband", "Telefon", "Försäkring", "Gym", "Disponent", "Avfall", "Tandvård"], "forms": ["Ab", "Abp"],
        "lines": ["Grundavgift", "Förbrukning", "Serviceavgift"], "ask": "Förbered den här räkningen för betalning",
    },
    "en": {
        "title": "INVOICE", "payee": "Payee", "iban": "Payee's account (IBAN)", "ref": "Reference number", "due": "Due date", "sum": "Amount due",
        "pay": "PAYMENT DETAILS", "customer": "Customer", "number": "Invoice number", "dated": "Invoice date", "note": "A sample invoice for a demo. The company, the customer and the account are made up.",
        "kinds": ["Power", "Water", "Heating", "Broadband", "Mobile", "Insurance", "Gym", "Housing", "Waste", "Dental"], "forms": ["Ltd", "Oy"],
        "lines": ["Basic fee", "Usage", "Service fee"], "ask": "Get this bill ready to pay",
    },
}
FIRST = ["Demo", "Esimerkki", "Malli", "Testi", "Kuvitteellinen", "Sample", "Exempel"]
FONTS = ["Arial, Helvetica, sans-serif", "Georgia, 'Times New Roman', serif", "Verdana, Geneva, sans-serif", "'Trebuchet MS', sans-serif", "'Courier New', monospace"]
MONO = ["'Courier New', monospace", "Consolas, monospace", "Arial, Helvetica, sans-serif", "Georgia, serif"]
PAPER = ["#fbfaf6", "#ffffff", "#f4f1e8", "#f7f9fb"]
DESK = [("#8a847b", "#5d5850"), ("#6c7a86", "#3f4a54"), ("#b9b2a4", "#8d8676"), ("#4a4a4a", "#262626")]


def money(amount: float, lang: str) -> str:
    whole, cents = f"{amount:,.2f}".split(".")
    if lang == "en":
        return f"€{whole}.{cents}"
    return f"{whole.replace(',', ' ')},{cents} €"


def make(n: int, rng: random.Random) -> dict:
    lang = rng.choices(["fi", "sv", "en"], [6, 2, 2])[0]
    w = WORDS[lang]
    payee = f"{rng.choice(FIRST)} {rng.choice(w['kinds'])} {rng.choice(w['forms'])}"
    iban = iban_fi("99" + "".join(rng.choice("0123456789") for _ in range(12)))
    if rng.random() < 0.12:
        reference = rf_reference("".join(rng.choice("0123456789") for _ in range(rng.randint(6, 16))))
        shown_ref = grouped(reference)
    else:
        reference = fi_reference(str(rng.randint(1, 9)) + "".join(rng.choice("0123456789") for _ in range(rng.randint(3, 18))))
        shown_ref = grouped(reference, 5, from_right=True)
    amount = round(rng.choice([rng.uniform(5, 120), rng.uniform(5, 120), rng.uniform(120, 900), rng.uniform(900, 4800)]), 2)
    due = dt.date(2026, 10, 1) + dt.timedelta(days=rng.randint(0, 100))
    if lang == "en":
        shown_due = f"{due.day} {due.strftime('%B')} {due.year}"
    else:
        shown_due = rng.choice([f"{due.day}.{due.month}.{due.year}", f"{due.day:02d}.{due.month:02d}.{due.year}"])
    parts = sorted(round(rng.uniform(0.15, 0.6) * amount, 2) for _ in range(2))
    lines = list(zip(w["lines"], [parts[0], parts[1], round(amount - sum(parts), 2)]))
    return {
        "n": n, "lang": lang, "ask": w["ask"],
        "truth": {"payee": payee, "iban": iban, "reference": reference, "amount": amount, "due_date": due.isoformat()},
        "shown": {"iban": grouped(iban), "reference": shown_ref, "amount": money(amount, lang), "due": shown_due, "lines": [(a, money(b, lang)) for a, b in lines]},
        "look": {
            "layout": rng.choice(["box", "side", "table"]), "font": rng.choice(FONTS), "mono": rng.choice(MONO), "paper": rng.choice(PAPER), "desk": rng.choice(DESK),
            "tilt": round(rng.uniform(-3.5, 3.5), 2), "blur": rng.choice([0, 0, 0.3, 0.6]), "quality": rng.choice([55, 68, 80, 90]), "scale": rng.choice([0.85, 1.0, 1.0, 1.1]),
        },
    }


def html(bill: dict) -> str:
    w, s, k, t = WORDS[bill["lang"]], bill["shown"], bill["look"], bill["truth"]
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in s["lines"])
    details = (
        f"<tr><td class=k>{w['payee']}</td><td class=v>{t['payee']}</td></tr>"
        f"<tr><td class=k>{w['iban']}</td><td class=v>{s['iban']}</td></tr>"
        f"<tr><td class=k>{w['ref']}</td><td class=v>{s['reference']}</td></tr>"
        f"<tr><td class=k>{w['due']}</td><td class=v>{s['due']}</td></tr>"
        f"<tr class=sum><td class=k>{w['sum']}</td><td class=v>{s['amount']}</td></tr>"
    )
    pay = f"<div class='pay {k['layout']}'><h2>{w['pay']}</h2><table>{details}</table></div>"
    lines = f"<table class=lines>{rows}</table>"
    meta = (
        f"<table><tr><td class=k>{w['customer']}</td><td>Demo Asiakas<br>Mallitie 2 A 3, 02100 Espoo</td></tr>"
        f"<tr><td class=k>{w['number']}</td><td>2026-{bill['n'] + 100000}</td></tr><tr><td class=k>{w['dated']}</td><td>28.9.2026</td></tr></table>"
    )
    body = {"box": meta + lines + pay, "side": pay + meta + lines, "table": meta + pay + lines}[k["layout"]]
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;font-family:{k['font']};}}
.desk{{width:1100px;height:1400px;display:grid;place-items:center;background:radial-gradient(circle at 30% 20%,{k['desk'][0]},{k['desk'][1]});}}
.paper{{width:820px;min-height:1060px;background:{k['paper']};color:#1b1b1b;padding:54px 58px;box-sizing:border-box;
transform:rotate({k['tilt']}deg) scale({k['scale']});filter:blur({k['blur']}px);box-shadow:0 30px 60px rgba(0,0,0,.45);}}
.top{{display:flex;justify-content:space-between;border-bottom:3px solid #1b1b1b;padding-bottom:16px}} h1{{font-size:38px;margin:0}}
.brand{{font-size:27px;font-weight:700}} table{{width:100%;border-collapse:collapse;margin-top:22px;font-size:18px}}
td{{padding:8px 0;vertical-align:top}} td.k{{color:#555;width:46%}} .lines td{{border-bottom:1px solid #d8d5cc}} .lines td:last-child{{text-align:right}}
.pay{{margin-top:28px;border:2px solid #1b1b1b;padding:18px 20px}} .pay.side{{border-width:0 0 0 6px;background:rgba(0,0,0,.04)}} .pay.table{{border-width:2px 0}}
.pay h2{{margin:0 0 6px;font-size:19px;letter-spacing:1px}} .pay td{{font-size:20px}} .pay td.v{{font-weight:700;font-family:{k['mono']};font-size:22px}}
.sum td.v{{font-size:28px}} .fine{{margin-top:22px;font-size:13px;color:#666}}
</style><div class="desk"><div class="paper"><div class="top"><div class="brand">{t['payee']}</div><h1>{w['title']}</h1></div>{body}<div class="fine">{w['note']}</div></div></div>"""


def bills(count: int) -> list[dict]:
    rng = random.Random(SEED)
    return [make(n, rng) for n in range(count)]


def render(count: int) -> None:
    from playwright.sync_api import sync_playwright

    WORK.mkdir(parents=True, exist_ok=True)
    made = bills(count)
    (WORK / "bills.json").write_text(json.dumps(made, ensure_ascii=False), encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1400})
        for bill in made:
            page.set_content(html(bill))
            page.screenshot(path=str(WORK / f"bill-{bill['n']:04d}.jpg"), type="jpeg", quality=bill["look"]["quality"])
        browser.close()
    print(f"{count} bills in {WORK}")


# -------------------------------------------------------------------- the run ---


def clean(value) -> str:
    return re.sub(r"[\s.\-]", "", str(value or "")).upper()


def run(shard: int, shards: int, only: set[int] | None = None, name: str = "results") -> None:
    sys.path.insert(0, str(ROOT))
    from app import agent, db

    db.init()
    made = json.loads((WORK / "bills.json").read_text(encoding="utf-8"))
    out = WORK / f"{name}-{shard}.jsonl"
    done = {json.loads(line)["n"] for line in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
    with out.open("a", encoding="utf-8") as f:
        for bill in made:
            if bill["n"] in done or (only is not None and bill["n"] not in only) or (only is None and bill["n"] % shards != shard):
                continue
            photo = "data:image/jpeg;base64," + base64.b64encode((WORK / f"bill-{bill['n']:04d}.jpg").read_bytes()).decode()
            started = time.time()
            row: dict = {"n": bill["n"], "lang": bill["lang"]}
            try:
                events = list(agent.run("CUST00086", bill["ask"], [], image=photo))
                answer = next(e for e in reversed(events) if e["type"] == "answer")
                drafts = [e["result"] for e in events if e["type"] == "tool_result" and e["name"] == "prepare_payment"]
                row.update(mode=answer.get("mode"), host=answer.get("served_by"), tools=[e["name"] for e in events if e["type"] == "tool_call"])
                row["numbers_checked"] = bool((answer.get("grounding") or {}).get("ok"))
                row["attempts"] = len(drafts)
                if drafts:
                    # What the customer would see: the last draft of the turn.
                    last, t = drafts[-1], bill["truth"]
                    d = last.get("draft") or {}
                    row["shown"] = {k: d.get(k) for k in ("payee", "account_number", "reference", "amount", "due_date")}
                    row["ok"] = {
                        "payee": " ".join(str(d.get("payee") or "").split()).lower() == t["payee"].lower(),
                        "iban": clean(d.get("account_number")) == t["iban"],
                        "reference": clean(d.get("reference")) == t["reference"],
                        "amount": isinstance(d.get("amount"), (int, float)) and abs(d["amount"] - t["amount"]) < 0.005,
                        "due_date": d.get("due_date") == t["due_date"],
                    }
                    row["ready"] = bool(last.get("ready_to_confirm"))
                    row["first_ready"] = bool(drafts[0].get("ready_to_confirm"))
                    row["checks"] = {k: (last.get("checks") or {}).get(k) for k in ("account_number", "reference", "amount", "due_date")}
                    if last.get("error"):
                        row["tool_error"] = str(last["error"])[:160]
            except Exception as exc:  # noqa: BLE001: one bad bill must not stop the run
                row["error"] = f"{type(exc).__name__}: {exc}"[:200]
            row["seconds"] = round(time.time() - started, 1)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()


# ----------------------------------------------------------------- the report ---

PAYMENT = ("iban", "reference", "amount", "due_date")


def report(name: str = "results") -> None:
    rows = []
    for path in sorted(WORK.glob(f"{name}-*.jsonl")):
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["n"])
    model = [r for r in rows if r.get("mode") == "nemotron"]
    drafted = [r for r in model if "ok" in r]
    right = lambda r: all(r["ok"][k] for k in PAYMENT)  # noqa: E731
    ready = [r for r in drafted if r["ready"]]
    ready_right = [r for r in ready if right(r)]
    ready_wrong = [r for r in ready if not right(r)]
    held = [r for r in drafted if not r["ready"]]
    seconds = sorted(r["seconds"] for r in model)
    s = {
        "bills": len(rows),
        "answered_by_the_model": len(model),
        "a_draft_was_prepared": len(drafted),
        "ready_to_confirm": len(ready),
        "ready_and_every_payment_field_right": len(ready_right),
        "ready_with_a_wrong_payment_field": len(ready_wrong),
        "held_back_for_the_customer_to_check": len(held),
        "of_those_held_back_were_in_fact_right": sum(right(r) for r in held),
        "needed_a_second_look_at_the_photo": sum(r.get("attempts", 1) > 1 for r in drafted),
        "per_field_right": {k: sum(r["ok"][k] for r in drafted) for k in ("payee", *PAYMENT)},
        "answers_with_every_number_checked": sum(bool(r.get("numbers_checked")) for r in model),
        "errors": sum("error" in r for r in rows),
        "median_seconds": seconds[len(seconds) // 2] if seconds else None,
        "answered_by": {
            host: sum(1 for r in model if r.get("host") == host) for host in sorted({str(r.get("host")) for r in model})
        },
        "by_language_ready_and_right": {
            lang: f"{sum(1 for r in ready_right if r['lang'] == lang)}/{sum(1 for r in rows if r['lang'] == lang)}" for lang in ("fi", "sv", "en")
        },
    }
    keep = {"summary": s, "ready_with_a_wrong_field": ready_wrong, "held_back": held, "no_draft": [r for r in rows if "ok" not in r]}
    (ROOT / "eval" / "bill-reading.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
    f = s["per_field_right"]
    hosts = ", ".join(f"{count} by {host}" for host, count in s["answered_by"].items())
    which = (
        f'These are the bills of the set "{SET}": made by the same generator as the bills the checks were tuned on, but other bills, '
        "which nobody had looked at before this run."
        if SET
        else "These are the bills the checks were tuned on."
    )
    text = f"""# Reading bills from photos

{s['bills']} made-up bills, each sent through the app with the picture and the question a customer would ask ("get this bill ready to pay").
The bills are rendered, not photographed: three layouts, Finnish, Swedish and English, five typefaces, tilted up to 3.5 degrees, some
slightly blurred, JPEG quality 55 to 90. Every company, customer and account is invented. Produced by `python scripts/bill_reading_test.py`.
{which}

What is judged is the draft the customer would see: the account number, the reference, the amount and the due date on it, against what
was printed on the bill.

| | |
|---|---|
| Bills | {s['bills']} |
| A draft was prepared | {s['a_draft_was_prepared']} |
| Ready to confirm | {s['ready_to_confirm']} |
| ... and every payment field right | {s['ready_and_every_payment_field_right']} |
| ... with a wrong payment field | {s['ready_with_a_wrong_payment_field']} |
| Held back for the customer to check or photograph again | {s['held_back_for_the_customer_to_check']} |
| ... of which the draft was in fact right | {s['of_those_held_back_were_in_fact_right']} |
| The model was sent back to the photo after a failed check | {s['needed_a_second_look_at_the_photo']} |
| Account number / reference / amount / due date right on the draft | {f['iban']} / {f['reference']} / {f['amount']} / {f['due_date']} |
| Payee's name exactly as printed (it has no check; the customer sees it) | {f['payee']} |
| Answers in which every number was traced to the tool result | {s['answers_with_every_number_checked']} |
| Median time for the whole answer, with eight bills in flight at once | {s['median_seconds']} s |
| Ready and right, by language of the bill (fi / sv / en) | {' / '.join(s['by_language_ready_and_right'][k] for k in ('fi', 'sv', 'en'))} |

How a draft becomes "ready":

1. The model reads the bill and passes the payee, the account number, the reference, the total and the due date to the engine.
2. The engine recalculates the check digits inside the account number and the reference.
3. The amount and the due date have no check digit, so the model is asked a second time, for something simpler: to copy the bill's
   text line by line. The engine finds the total and the due date in that text by their labels, and both readings must agree.
4. The total may not be smaller than another amount printed on the bill, and the due date must be after the bill's own date.
5. A draft that fails any of this goes back to the photo once. If it fails again, it is shown without a confirm button.

All answers came from Nemotron 3.5 Super VL: {hosts}. The run used our second host so that the public demo stayed fast, and that
host passed requests on to NVIDIA's hosted API when it was busy with eight bills at once.
Every draft that was not ready is listed in `eval/bill-reading.json`.
"""
    (ROOT / "eval" / "bill-reading.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "render":
        render(int(sys.argv[2]) if len(sys.argv) > 2 else 1000)
    elif command == "run":
        run(int(sys.argv[2]), int(sys.argv[3]))
    elif command == "some":  # chosen bills only: python scripts/bill_reading_test.py some 177,211,46 [name]
        run(0, 1, only={int(x) for x in sys.argv[2].split(",")}, name=sys.argv[3] if len(sys.argv) > 3 else "some")
    elif command == "report":
        report(sys.argv[2] if len(sys.argv) > 2 else "results")
    else:
        print(__doc__)
