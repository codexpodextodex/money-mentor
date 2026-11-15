# The pitch deck

Fourteen slides, 16:9, in the look of the film (`video/`): `out/money-mentor-deck.pdf`, and `out/slide-01.png` to `slide-14.png` (1920 x 1080, rasterised from the PDF).

`out/` and `screens/` are not in git. The deck carries S-Pankki's logo and typefaces, so share the file, not a public page of it.

## Build it again

From the project folder, with `web/brand/` in place:

```bash
python deck/build.py
```

That prints the PDF, checks it and writes the fourteen PNGs. It uses the app screens already photographed in `deck/screens/`. To photograph them again from the running app (http://127.0.0.1:8791) and then build:

```bash
python deck/build.py --capture
```

Or only some of them, and then build: `python deck/capture.py bill` followed by `python deck/build.py`.

It needs the system Python with Playwright (and its Chromium), Pillow, PyMuPDF and reportlab. It installs and downloads nothing.

## How it is made

| File | What it is |
|---|---|
| `deck.html` | The fourteen slides: every word on them |
| `deck.css` | Layout, colour and type, taken from `video/film.css` |
| `capture.py` | Photographs the app's screens at three times phone size into `screens/`, with each screen's text (`*.txt`) and the engine's JSON (`figures.json`) |
| `build.py` | Serves the page, checks it, prints the PDF with headless Chromium, checks the PDF and rasterises it |

- The phone is the film's: `build.py` serves `video/device.js` and the page draws the shell with it. The logo and the fonts are read from `web/brand/`, the sample price tag and the sample bill from `web/img/`. Nothing is copied into `deck/`.
- Every screen in a phone is a photograph of the running app, taken through the `postMessage` contract in `web/README.md` and shown as it is: not redrawn, not edited. The only thing done to a screen is scrolling it to the part the slide is about. The clock, the signal icons and the home bar belong to the phone shell, as in the film.
- The four chat answers are written by the model, so `capture.py` asks until it gets a take in clean English, as `video/capture.py` does. The figures do not vary. For the bill (`bill`) a take also has to say in its own words that nothing is paid yet, and show the draft card with both numbers and its button. For the jacket (`when`) a take also has to open with the tool's verdict and must not have the jacket filed under Home & Tech, which the model does now and then: the card's small print would then be about tech.
- `build.py` stops if `web/brand/` is incomplete, and reports a problem if any text on a slide is set in another typeface, runs into a phone or leaves the slide, if a link is missing, or if the QR code in the PDF differs from the encoder's matrix.

## Which screen is in which phone

All for the default demo customer `CUST00086` on the demo's "today", 30 September 2026, except the price-tag photo (`CUST00874`, as in the film).

| Slide | Screen (`screens/*.png`) |
|---|---|
| 1 | `home`: the home screen with the trainer card |
| 2 | `account`: S-Tili and its list of payments |
| 3 | `trainer`: safe to spend this week |
| 4 | `notices`: the trainer scrolled to "Worth a look"; `outlook`: the payday plan scrolled to "The weeks ahead" |
| 5 | `replay` |
| 6 | `ask`: the answer to "How much did I spend on fast food in the last 3 months?", scrolled to its card |
| 7 | `photo`: the answer to the sample price tag for `CUST00874`, scrolled to its card |
| 8 | `when`: the answer to "Can I afford a €120 jacket?", scrolled to the bars of its card, so the "When it could fit" block and the checked-numbers line are in view |
| 9 | `bill`: the answer to the sample bill (`web/img/sample-bill.jpg`) sent with "Get this bill ready to pay", scrolled to its payment draft card. The bill itself is shown beside the phone, as the price tag is on slide 7 |
| 10 | `loan`: the home loan screen |
| 13 | `home-fi` (Finnish), `bank-sv` (Swedish, the Bank tab), `trainer` (English) |

## Where every figure comes from

| Slide | On the slide | Source |
|---|---|---|
| 1, 11, 14 | 65/65 test questions right | `eval/results.md`, row "model-checked" (what the app runs): 65 questions, 100% right tool, arguments and number |
| 1, 11, 14 | 2.3 s median answer | `eval/results.md`: 2.25 s for "model-checked" |
| 1, 12, 14 | An open model, hosted in Finland; NVIDIA Nemotron 3.5 Super VL, open weights, served with vLLM on a Verda confidential-computing GPU in Finland (RTX PRO 6000, encrypted memory) | `SUBMISSION.md`, "NVIDIA: how we used Nemotron" and "Verda: process summary"; `/api/health` lists the hosts |
| 1, 14 | 95-216-229-240.sslip.io | The public demo (`SUBMISSION.md`) |
| 2 | 387,000 people with a payment default, Finland, end of June 2026 | Suomen Asiakastieto, as reported by Yle News on 22 July 2026 (`video/README.md`) |
| 3 | Balance €1,402 | `screens/account.txt`: €1,402.38, rounded as the app's own payday plan shows it ("Balance today €1,402") |
| 3 | Safe to spend this week €0 | `screens/trainer.txt` |
| 3 | €899 a month, 65%; €61.31 a month, 4%; €418 a month, 30% | `screens/trainer.txt`, "Where your money goes" (July to September 2026) |
| 4 | Balance runs out around 14 October; housing payment about €967 around 4 Oct; about €40 a week instead of €98 | `screens/notices.txt`, the first notice in "Worth a look" |
| 4 | A plan for the salary, one tap to accept | `screens/outlook.txt` (the payday plan screen: "Accept the plan") |
| 5 | 64 days below zero become 32; €852 kept over the year | `screens/replay.txt` |
| 6 | 5 payments, €88.90 | `screens/ask.txt` |
| 7 | If you need it: It fits. If it is a treat: Tight | `screens/photo.txt` (`CUST00874`) |
| 7 | For the first customer the answer is "Not now" | The same photo asked as `CUST00086` on 14 Nov: "Not now. After the bills due before payday your balance covers €179" |
| 8 | A €120 jacket: not from this pay period's budget | `screens/when.txt`: the answer opens "Not from this pay period's everyday budget."; the card says "Over budget", "This purchase €120", "Safe until payday (15 Oct) €0" |
| 8 | Not from the next salary either. With one habit changed, in about 2 months | `screens/when.txt`, the card's "When it could fit" block: "In about 2 months, with one habit changed", "Not from the next salary either." The engine's `check_affordability` for `CUST00086` and 120: `when.route` is `one_habit`, `months_for_this_price` is 2 |
| 8 | Your own last 12 months replayed, not a forecast and not a promise | The tool's own `how_to_read` (`PAST_NOT_PROMISE` in `app/plan.py`); on the screen: "over your last 12 months" and "This is your own past replayed, not a promise." |
| 8 | S-Pankki's team asked for this at our booth on Saturday. It was live the same evening. | The team's own account of Saturday 14 Nov 2026. Nothing in the app or the data shows it: change the line if the day or the timing is told differently |
| 9 | The model reads the payee, the account number, the reference, the amount and the due date | `screens/bill.txt`: the card shows Demo Sähkö Oy, €84.60, due 12 Oct 2026, FI87 9999 9900 0123 44 and 20261 04577, the same as on the sample bill (`scripts/make_sample_bill.py`) |
| 9 | The engine recalculates the check digits in the account number and the reference, so a misread digit is caught | `app/bills.py` (`check_iban`, `check_reference`) and `tests/test_bills.py`; on the screen both numbers carry "Checks out" and the line "The check digits inside both numbers were recalculated, so a misread digit is caught." |
| 9 | You look it over and confirm; in this demo nothing is paid | `screens/bill.txt`: "Draft · not paid", "Confirm the payment", "In this demo nothing is paid."; the tool's own `nothing_is_paid`. Pressing the button in the app only shows "Nothing was paid" |
| 9 | On Saturday we described this to S-Pankki's team as an idea. It works in the demo now. | The team's own account of Saturday 14 Nov 2026. Nothing in the app or the data shows it: change the line if the day is told differently |
| 10 | 200 real application outcomes; income, own money, collateral, money habits; guidance, not a credit decision | `screens/loan.txt`: "learned from 200 real home loan applications in the data: 150 approved and 50 turned down" |
| 11 | 19 tools | `/api/health` (`screens/figures.json`, `health.tools`): `prepare_payment` is the nineteenth |
| 11 | 69% right tool for a keyword baseline | `eval/results.md`, row "router": 69.2% |
| 11 | 94% and 100% of answers with every number traceable | `eval/results.md`: 93.8% for "model-minimal" and "model-coach" (no number check), 100% for "model-checked" |
| 11 | 14 Nov 2026, 65 questions, 5 held-out customers, three languages | `eval/results.md`, `SUBMISSION.md` |
| 12 | Only the chat calls the model | `app/server.py`: only `POST /chat` goes to `app/agent.py`; every other screen reads the engine's endpoints |
| 14 | The five criteria | `SUBMISSION.md`, "What each one asks for" |

If the evaluation is run again or the app's figures change, change them in `deck.html` and build again.

The product slides carry the numbers 01 to 08 in their eyebrows. "When it could fit" (slide 8) is 06, "A bill, from a photo" (slide 9) is 07, so the home loan (slide 10) became 08.

## What was checked, and what was not

Checked on 14 Nov 2026: every page of the PDF looked at as a picture; every figure against the sources above; every screen's text against the film's frozen copy of the same screen (the same, apart from the model's wording in the two chat answers); fonts, links, page size and QR modules by `build.py`.

Checked again the same evening, after slide 8 ("When it could fit") was added: every page of the 13-page PDF looked at as a picture; slide 8's figures against `screens/when.txt` and the engine's result; and the other twelve pages compared pixel by pixel with the 12-slide build. They are the same apart from the page number, and on slide 9 the eyebrow's number (06 became 07, which moves that one line of text by two pixels). Only `when` was photographed for this build: the other screens are the earlier photographs. The film has no copy of the `when` screen to compare with.

Checked again on 14 Nov, after slide 9 ("A bill, from a photo") was added: every page of the 14-page PDF looked at as a picture; slide 9's words against `screens/bill.txt`; and the other thirteen pages compared pixel by pixel with the 13-slide build. They are the same apart from the page number, and three edits: on slide 10 the eyebrow's number (07 became 08), on slide 11 "Nemotron picks from 19 tools" (it was 18), and on slide 14 the "Next · not built" line, which now names only the nudge for an unpaid regular bill. Only `bill` was photographed for this build: the other screens are the earlier photographs. The film has no copy of the `bill` screen to compare with. The 65-question evaluation on slides 1, 11 and 14 was run before `prepare_payment` existed and has no bill question in it.

Not checked: nobody has scanned the QR code with a phone (there is no decoder on this machine; the modules in the PDF match the encoder's output). The PDF was looked at as rendered by PyMuPDF, not in Acrobat, Preview or a browser.
