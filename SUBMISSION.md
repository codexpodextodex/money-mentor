# Submission checklist

Junction 2026, team Moonshot (table A78). Draft "Money Mentor" on hackjunction.app. **Final deadline: Sunday 15 Nov, 10:00.** Drafts are not reviewed: switch to FINAL.

One project, three entries:

| Entry | Type | Prize |
|---|---|---|
| S-Pankki: Personal Economic Trainer | Main challenge | Airbnb gift cards, EUR 2,000 / 1,000 / 500 |
| NVIDIA: Best Use of Nemotron | Tech challenge | One RTX 5080 for each of the two best teams |
| Verda Compute Track: Best use of Verda | Tech challenge | Cloud credits, USD 10,000 / 2,500 / 2,500 |

## What each one asks for

**S-Pankki**, 20% each: impact on financial literacy (including the teaching angle), originality of AI integration, clarity of the mobile user experience, feasibility, potential to integrate into S-mobiili.

**NVIDIA**, minimum requirements:
1. Nemotron 3.5 Super VL is used in the working solution.
2. The demo shows its contribution to the core functionality.
3. A short text in the submission form: the model used, what it does, why it matters, how its outputs were improved.

Judged on: meaningful Nemotron usage, technical execution, quality of AI output (prompting, evaluation, feedback loops), creativity and differentiation.

**Verda**, minimum requirements: document the process, and post a link to a summary in the Discord `#verda` channel. They look for an idea where compute matters, the right Verda product with a reason, the path from idea to prototype, and how it would scale.

## To do, in order

- [x] Self-serve NVIDIA key in `.env`; `python scripts/check_model.py` passes (tools and image input).
- [x] First evaluation run (3 customers); table is in the README.
- [ ] Verda key from ElliotNVIDIA (asked by DM and in `#nvidia` on 14 Nov, no reply yet). When it arrives, switch `.env` to option A and run `check_model.py` again.
- [ ] Put the evaluation table (README) in the deck.
- [x] S-Pankki's logo and typeface: the team has the bank's permission (14 Nov). The files are in `web/brand/`, which git ignores, so they are not in the public repository. Whoever deploys the demo must deploy from a folder that has them.
- [x] Test the photo feature with a price tag (14 Nov: a generated shelf-tag photo, 349,00 €; the model read item and price and answered in about 5 s in English and Finnish). Still worth one try with a phone photo of a real tag.
- [x] Verda: account and credits (EUR 200), and Nemotron running in a Verda serverless container on an RTX PRO 6000 since 14 Nov, 05:34 (see `deploy/verda.md`). The app asks it first and falls back to NVIDIA's API.
- [x] Evaluation rerun against the Verda-hosted model with 5 customers (table in the README).
- [x] Verda: the app is hosted on a small Verda machine. **Public demo link: https://95-216-229-240.sslip.io** (14 Nov, 06:15). After local changes run `deploy/push_app.sh 95.216.229.240`.
- [ ] After judging (Sunday 14:00), delete both Verda resources so the charges stop: the model ($3.09 an hour) and the app machine ($0.05 an hour). The commands are at the top of `deploy/verda.md`.
- [x] Repository on GitHub, private for now: https://github.com/codexpodextodex/money-mentor (14 Nov).
- [ ] Make the repository public just before submitting (`gh repo edit codexpodextodex/money-mentor --visibility public --accept-visibility-change-consequences`). Junction needs it public with the MIT licence.
- [ ] Record a phone-sized demo and the pitch video (2:00 at most, public link).
- [ ] Deck as PDF.
- [ ] Show the demo at the NVIDIA table and the S-Pankki booth (5th floor) on Saturday.
- [ ] Platform: name, punchline, description, challenge, demo link, source link, video link, deck, tech challenges ticked, NVIDIA text.
- [ ] Post the process summary link in `#verda`.
- [ ] Switch the draft to FINAL before Sunday 10:00.
- [ ] Whole team at the venue for peer review, Sunday 10:30 to 14:00.

## Draft texts

The evaluation figures below are from the run on 14 Nov 2026 against the Verda-hosted model (`eval/results.md`). If the evaluation is run again, update them. Text still in square brackets in the Verda section must be filled in before submitting.

### Punchline (200 characters max)

Chat with your own money. An open model explains, a deterministic engine does the maths, and every number in every answer is checked against your own transactions.

### NVIDIA: how we used Nemotron

Model: NVIDIA Nemotron 3.5 Super VL (the open NVFP4 weights), which we serve ourselves with vLLM on a Verda GPU in Finland. NVIDIA's hosted API is the fallback.

What it does: Nemotron is the coach. It reads a customer's question in Finnish, Swedish or English, chooses among 16 tools over the customer's own transactions (often several at once), reads the JSON results and explains them in S-Pankki's three-basket frame with one concrete next step. It also reads photos: the customer photographs a price tag, a receipt or a bill, Nemotron reads the item and the price, and the engine answers "can I afford this?" against what is safe to spend this week.

Why it matters: a bank cannot send customer transactions to a third-party API, and it cannot ship a model that invents a number. An open-weight model that the bank runs itself solves the first. Our division of labour solves the second: Nemotron never calculates, it only decides what to look up and how to explain it.

How we improved its outputs:
1. A coach prompt that fixes the division of labour and the shape of an answer.
2. Tool descriptions written in the customer's words, and tool errors that say how to fix the call, so the model corrects itself.
3. A number check: every number in an answer is traced to a tool result. An untraceable number triggers one rewrite, and if it survives it is flagged in the app.
4. An evaluation with known answers: 13 questions for each of 5 held-out customers, in English, Finnish and Swedish (65 questions per system, run on 14 Nov 2026 against the model we host on Verda). Nemotron chose the right tool and arguments in all 65, against 69% for a keyword baseline. Answers in which every number could be traced to the data: 91% with a bare prompt, 95% with the coach prompt, 100% with the number check, which rewrote three answers. Median answer time 1.9 seconds.
5. A formatting pass after the model: amounts are rewritten in the answer's own language style (€1,234.56 or 1 234,56 €), because a Finnish price tag in a photo pulled English answers towards Finnish number formats. The pass never changes a value, and a test checks that.
6. Speed: switching the model's extra reasoning off for this tool-calling job took answers from about 10 seconds to about 3 with the same tool choices in our tests, and hosting the model ourselves took the median to 1.9.

### Verda: process summary

- What runs on Verda: Nemotron 3.5 Super VL (120B parameters, NVIDIA's NVFP4 build, 75 GB) served with vLLM in a serverless container on one RTX PRO 6000 in Finland, and the app itself on a small CPU instance in the same region (https://95-216-229-240.sslip.io). A question asked on the public demo is answered by our own model in about 1.5 seconds.
- Why compute matters: a bank cannot send customer transactions to a third-party API. Running an open-weight model on infrastructure it controls is what makes "chat with your money" possible at all, and it was also faster: median answer 1.9 seconds on our own replica, against 2.7 in an earlier run of the same evaluation through the hosted API.
- Why this Verda product: a serverless container gives an OpenAI-compatible endpoint with no server to look after, scales replicas with demand (payday peaks) and to zero when idle. One RTX PRO 6000 at $3.09 an hour is the cheapest card NVIDIA lists for this model.
- Path, as it happened on Saturday morning: (1) Verda's hosted inference has no Nemotron, so we host it. (2) First try: a confidential-computing RTX PRO 6000 machine, because a confidential GPU is the right story for a bank. The machine was up in 36 seconds and pulled 75 GB of weights in 2.5 minutes. vLLM loaded the model but answered in junk. Two hours of elimination showed it was not the model, the 4-bit weights or our flags: a small standard model failed the same way under vLLM, while plain PyTorch on the same GPU was correct. Cost: about EUR 4. (3) Second try: the same image and command as a serverless container on an ordinary RTX PRO 6000. Healthy in 12 minutes, correct answers, tool calls and image reading. (4) The app now asks the Verda model first and falls back to NVIDIA's API if the replica is asleep. Notes and commands: `deploy/verda.md` in the repository.
- Scale: the engine is stateless SQL over Parquet and the model endpoint is OpenAI-compatible, so the app and the model scale separately. One replica is set to take 16 requests at once; more replicas are one setting. For a bank, the open question we would take to Verda is the confidential-computing path.
- [Total Verda spend and hours, filled in at the end.]

### Pitch in one breath

No Finnish bank lets you talk to your own money. Money Mentor does, and it teaches as it answers: essentials first, a buffer for the unexpected, and everyday spending is what is left. The model explains, the engine does the maths, and you can see the working behind every number.
