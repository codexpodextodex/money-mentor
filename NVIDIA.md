# Money Mentor and NVIDIA Nemotron 3.5 Super VL

Junction 2026 · Best Use of Nemotron · Team Moonshot

Money Mentor is a money trainer inside a bank's mobile app. A customer asks about their own money in Finnish, Swedish or English, or photographs a price tag in a shop, and gets an answer in about two seconds in which every number has been checked against their own payments.

**Nemotron is the brain of the product. Every answer in the chat is its work, and so is every photo that gets read. It runs on our own GPU, not through someone else's API.**

Try it: https://95-216-229-240.sslip.io (press "Start the walkthrough", or open "Ask your money" and type).

## The four things the challenge asks for

**The model.** NVIDIA Nemotron 3.5 Super VL, the open NVFP4 weights (`nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`). We serve it ourselves with vLLM on a single RTX PRO 6000: first on a confidential-computing GPU in Finland, then in a serverless container, with NVIDIA's hosted API as the last fallback.

**What it does.** It reads the customer's question, chooses among 19 tools over the customer's own payments (several at once when the question needs it), reads the JSON that comes back and explains it in the bank's three-basket way of teaching, with one concrete next step. It also reads photos. From a price tag it reads the item and the price, and the engine answers "can I afford this?". From a bill it reads the payee, the account number, the reference, the total and the due date, and the engine turns them into a payment draft for the customer to confirm.

**Why it matters.** A bank has two hard limits. It cannot send customers' payments to somebody else's API, and it cannot ship a model that invents a number. Nemotron's open weights remove the first limit: the bank can run it on its own servers. Its tool use removes the second: Nemotron decides what to look up and how to explain it, and never does arithmetic. And because one model handles text, tools and images, there is one thing to host, test and audit, not three.

**How we improved its outputs.**

1. **Tools written for the model.** Tool descriptions use the customer's words, and a tool error says how to fix the call, so Nemotron corrects itself in the same turn.
2. **A number check.** Every number in an answer is traced to a tool result. If one cannot be traced, Nemotron is asked once to rewrite; if it survives, the app flags it to the customer. This took answers with every number traceable from 94% to 100% in our evaluation.
3. **An evaluation with known answers.** 65 questions for 5 held-out customers in three languages, with the expected tool, arguments and number taken from the engine. It is one command, so a change to the prompt can be checked in a few minutes.
4. **Reasoning off for this job.** Tool selection did not need the model's extra reasoning: switching it off took an answer from about 10 seconds to about 3 with the same tool choices in our tests, and hosting the model ourselves took the median to about 2.
5. **Guards found by testing, not guessing.** A photo answer must rest on a lookup (before the guard, 2 of 6 Finnish photo answers skipped it when the photo followed another question; after it, 24 of 24 looked the price up). A photo answer opens with what was read ("I read: Nordwave Q7 Wireless, €349.00"), built from what Nemotron passed to the tool, so the customer can correct a misread. An answer in the wrong language is asked for again once.
6. **Feedback from the bank, built the same day.** On Saturday S-Pankki's team asked what the coach says after a "no". The same evening the affordability tool returned when the purchase could fit (from the next payday, or by changing the one habit that mattered most in the customer's own year), and Nemotron leads with it. A follow-up question now gets a fresh lookup, so its numbers are checked like any others.
7. **A thousand bills, four rounds.** Reading a bill is where a model's mistake costs money, so we measured it and let the measurements decide the design. Every round is described under "Bills from photos" below: the first version offered 16 wrong drafts in 481 bills, the last one none in 1,000 bills it had never seen.
8. **A formatting pass that never changes a value.** Amounts are rewritten the way the answer's language writes them (€1,234.56 or 1 234,56 €). A test checks that no value changes.

## Against the judging criteria

### Meaningful Nemotron usage

Take Nemotron out and the chat is gone. The keyword router we keep as an emergency fallback picks the right tool for 69% of the same questions and gets 20% of the Finnish and Swedish ones right. Nemotron gets all of them.

### Technical execution

```text
question or photo
   → Nemotron picks tools (19 to choose from, several at once)
   → the engine computes from the customer's own payments (DuckDB over Parquet)
   → Nemotron explains the results
   → number check: every number traced to a tool result, one rewrite if not
   → the answer, with the payments it counted and "N numbers checked against your data"
```

- **Latency:** median 2.3 seconds for a whole answer, tool round trip included. With a photo, 2.3 to 5.6 seconds.
- **Error handling:** three hosts are asked in order. One that does not connect within 5 seconds is skipped and left alone for two minutes. Every answer records which host wrote it, and the app shows it under "How was this worked out?".
- **Data flow:** the model only ever sees one customer's rows, and only through the tools.
- **Serving:** vLLM 0.32.0 with the recipe for this card, including speculative decoding. On the confidential GPU we hit a vLLM bug that made the server answer in junk while reporting healthy; the cause and the one-setting workaround are in [`deploy/verda-confidential-gpu-report.md`](deploy/verda-confidential-gpu-report.md).
- **Tests:** 229 automated tests, including scripted-model tests for the photo guards and the bill checks.

### Quality of AI output

Our own evaluation, 14 November 2026 (`eval/results.md`, produced by `python scripts/evaluate.py`):

| System | Right tool | Right arguments | Right number | Every number traceable | Finnish and Swedish right | Median time |
|---|---|---|---|---|---|---|
| Keyword router, no model | 69% | 62% | 58% | 100% | 20% | 0.01 s |
| Nemotron, bare prompt | 100% | 100% | 100% | 94% | 100% | 2.25 s |
| Nemotron, coach prompt | 100% | 100% | 100% | 94% | 100% | 2.17 s |
| Nemotron, coach prompt and number check (what the app runs) | 100% | 100% | 100% | 100% | 100% | 2.25 s |

65 questions per system. It is a small sample and the figures move a little between runs: a direction, not a benchmark. Reruns on the same five customers after each later change (the "when it could fit" answer, then the bill tool, which made it 19 tools) had the full system right on all 65 again (`eval/results-after-when.md`, `eval/results-after-bills.md`).

Two things in that table are worth saying out loud. Nemotron chose the right tool with the right arguments on all 65 questions even with a bare prompt, among the 18 tools the app had then and in three languages (with the nineteenth, the rerun was right on all 65 again). And the last step from 94% to 100% did not come from a cleverer prompt: it came from checking the model's numbers and letting it fix its own answer.

### Bills from photos: the model reads, arithmetic decides

Photograph a bill, and the app prepares the payment for you to confirm. No account number to type and no virtual barcode. In the demo nothing is ever paid.

A misread digit in an account number sends money to the wrong place, so nothing Nemotron reads from a bill is trusted until it has been checked:

1. Nemotron reads the bill and passes the payee, the account number, the reference, the total and the due date to the engine.
2. The engine recalculates the check digits inside the account number (IBAN, mod 97) and the reference number.
3. The amount and the due date have no check digit. So Nemotron is asked a second time, for something simpler: to copy the bill's text line by line. The engine finds the total and the due date in that text by their labels, and both readings must agree.
4. The total may not be smaller than another amount printed on the bill, and the due date must be after the bill's own date.
5. A draft that fails any check goes back to the photo once, with the failed check as the instruction. If it fails again, the customer sees which field to compare with the bill, and there is no confirm button.

We tested it on made-up bills rendered in three layouts and three languages, with five typefaces, tilt, blur and JPEG compression, each one sent through the whole app. What is judged is the draft the customer would see.

| Round | Bills | Right and ready | Held back for the customer | Offered with a wrong field |
|---|---|---|---|---|
| 1. Check digits only | 481 | 443 | 22 | 16 |
| 2. Dates passed as printed, a second reading, date order | 510 | 471 | 37 | 2 |
| 3. The total may not be smaller than another amount | 1,000 | 913 | 83 | 4 |
| 4. The second reading is a copy of the text, parsed by rule | 1,000 fresh bills | 984 | 16 | 0 |

What each round taught us:

- **Round 1.** Every misread account number and reference was caught by its check digits. But the model swapped day and month when it converted a date like 10.12.2026 itself (12 drafts), and four times it took one line of the bill for the total.
- **Round 2.** The model now passes the date exactly as printed and the engine reads it. Two wrong amounts were left.
- **Round 3.** Four wrong amounts were left, all on bills over EUR 1,000: asked twice for "the total", the model chose the same line twice.
- **Round 4.** Copying text is an easier job than choosing a figure, and the choosing is now done by rule. The last round ran on 1,000 bills that nobody had looked at during the tuning: no draft was offered with a wrong account number, reference, amount or due date, and 15 of the 16 held back were in fact right.

The figures and the method are in `eval/bill-reading.md`, and `python scripts/bill_reading_test.py` reproduces them.

### Creativity and differentiation

- **The model never calculates.** The obvious design lets the model do the sums. Here it only chooses and explains, and the customer can see the working: the app ticks off the payments that were counted.
- **A bill becomes a payment draft.** The model reads it, check digits and a second reading verify it, and the customer confirms.
- **A camera in the shop.** Photograph a price tag and ask "can I afford this?". A large purchase gets two honest answers, one if it replaces something you need and one if it is a treat, because the price alone cannot tell.
- **Run where a bank could run it.** We did not stop at an API key. The 120-billion-parameter model runs on one GPU with encrypted memory, in Finland.

## What Nemotron made possible

- **One model for everything.** Finnish, Swedish and English text, tool calls, price-tag photos and bills, with no second model anywhere in the product.
- **Fast for its size.** The challenge page says the model "runs fast for its size". Measured on one RTX PRO 6000: a complete tool-calling answer in a median of 2.3 seconds.
- **Open weights.** This is the difference between a demo and something a bank could deploy. The same weights that answer on our GPU could answer on the bank's.

## Limits

- No fine-tuning: the model is used as released.
- The evaluation is ours, 65 questions, and has not been repeated by anyone else.
- The test bills are rendered pictures, not phone photos of paper, and all come from one generator. Nobody has tried a real bill.
- A payee's name has no check digit. On the 1,000 fresh bills it was copied exactly on 886 drafts; the customer sees the name on the draft.
- The last bill run used our second host, so that the public demo stayed fast. With eight bills in flight at once it passed 233 of the 1,000 on to NVIDIA's hosted API; the other 767 were answered by our own serverless container.
- With eight bill photos in flight at once on the confidential GPU, about 13 of 481 tool calls came back with garbled arguments. The checks caught them and the model was asked again. We did not find the cause.
- English photo answers are slower (about 5.7 seconds median in the walkthrough's sequence), because a Finnish price tag sometimes pulls the first answer into Finnish and it is asked for again.
