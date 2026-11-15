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

Judged on: meaningful Nemotron usage, technical execution, quality of AI output (prompting, evaluation, feedback loops), creativity and differentiation. 25% each. The form has no separate box for the text: it goes in the description.

**Verda**, minimum requirements: document the process, and post a link to a summary in the Discord `#verda` channel. They look for an idea where compute matters, the right Verda product with a reason, the path from idea to prototype, and how it would scale. Judged 25% each: ambition (how much compute let us do), fit (the right Verda services, used well), working prototype (it runs and the process is documented), path to scale.

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
- [x] Verda: Nemotron also runs on a confidential-computing RTX PRO 6000 machine since 14 Nov, 11:29, and the public demo asks it first (then the serverless container, then NVIDIA's API). Same 65 evaluation questions on both hosts: all right on both, 2.27 s against 2.08 s median (`eval/results-verda-confidential.md`).
- [ ] Send Verda the report on the vLLM bug on their confidential machines (`deploy/verda-confidential-gpu-report.md`), in `#verda` or at their booth.
- [ ] After judging (Sunday 14:00), delete all three Verda resources so the charges stop: the confidential machine (EUR 2.62 an hour), the serverless model ($3.09 an hour) and the app machine ($0.05 an hour). The commands are at the top of `deploy/verda.md`.
- [x] Repository on GitHub, private for now: https://github.com/codexpodextodex/money-mentor (14 Nov).
- [ ] Make the repository public just before submitting (`gh repo edit codexpodextodex/money-mentor --visibility public --accept-visibility-change-consequences`). Junction needs it public with the MIT licence.
- [ ] Record a phone-sized demo and the pitch video (2:00 at most, public link).
- [x] Deck as PDF: `deck/out/money-mentor-deck.pdf`, 14 slides (15 Nov). Rebuild with `python deck/build.py`.
- [x] Shown at the S-Pankki booth on Saturday 17:15.
- [ ] Show the demo at the NVIDIA table, and the confidential-GPU report at the Verda booth (third floor, booth 6).
- [ ] Platform: fill in the form as listed under "On the platform" below.
- [ ] Post the process summary link in `#verda`.
- [ ] Switch the draft to FINAL before Sunday 10:00.
- [ ] Whole team at the venue for peer review, Sunday 10:30 to 14:00.

## The texts to submit

Written on 14 Nov 2026 after reading the challenge pages and the submission form on hackjunction.app. Every figure is from `eval/results.md`, `eval/results-verda-confidential.md` and `deploy/verda.md`. If the evaluation is run again, update them here, in `NVIDIA.md` and in `VERDA.md`.

### On the platform: what to fill in and click

hackjunction.app, "Your Submissions", "Money Mentor".

| Field | What goes in |
|---|---|
| Project Name | Money Mentor (already there) |
| Punchline (200 characters at most) | The text below |
| Description (5,000 characters at most) | The text below, as plain text (the platform shows markdown marks as they are): plain language for the bank first, then a section for NVIDIA's judges and one for Verda's. There is no separate box for NVIDIA: their "short explanation as text input into the submission form" has to be in the description |
| Challenge | Personal Economic Trainer (already chosen) |
| Project Demo | https://95-216-229-240.sslip.io |
| Source Code | https://github.com/codexpodextodex/money-mentor (make it public first) |
| Video | The public link to the film, 2:00 at most |
| Other Link | https://github.com/codexpodextodex/money-mentor/blob/main/VERDA.md |
| Presentation | `deck/out/money-mentor-deck.pdf` (14 slides, under 3 MB; the limit is 20 MB) |
| Tech Challenge Participation | Tick "Best Use of Nemotron" and "Verda Compute Track" |
| "Would you like to take part in a developer roundtable after the project submissions?" | Appears when Nemotron is ticked, and is required. Yes |

Then "Save Draft", read it once, and "Submit Final" before Sunday 10:00. The form saves nothing until one of the two is pressed.

Verda also wants the summary link posted in Discord `#verda` (their minimum requirement). NVIDIA and Verda both judge 25% on each of four criteria; `NVIDIA.md` and `VERDA.md` are written against them.

### Punchline

Your bank app shows a list. Money Mentor tells you where you stand.

Other options:

- Ask your money anything. Every number in the answer is checked.
- A money trainer inside S-mobiili: know what is safe to spend this week, before it runs out.
- Know what you can spend this week, and get a heads-up before it runs out.

### Description

```text
Your bank app shows a list of payments. Money Mentor tells you where you stand.

It is a money trainer inside S-mobiili. You open the app you already use, and it answers the questions a list of payments cannot.


WHAT IT ANSWERS

What can I spend this week?
One number, after your bills and your savings goal. It follows S-Pankki's three baskets: essentials first, a buffer for the unexpected, and everyday spending is what is left.

Will my money last?
A heads-up before the balance runs out, with the bill that tips it and the weekly pace that avoids it. Before every payday, a plan for the salary.

Can I afford this?
Ask, or photograph the price tag in the shop. If the answer is no, it says when it could fit. S-Pankki's team asked for that on Saturday, and it was live the same evening.

Can I just photograph this bill?
Yes. The app reads the bill, checks the account number, the reference, the amount and the due date, and you confirm. No typing, no virtual barcode. In a test of 1,000 bills, none was offered with a wrong field. In the demo nothing is paid.

Where did it go?
Ask anything in your own words, in Finnish, Swedish or English. "How much did I spend on fast food?" "What did I buy on 10 July?"

What would have helped?
Your own last year, replayed with one habit changed: 64 days below zero become 32.

Could I get a home loan?
Where you stand before you apply, compared with the application outcomes in the bank's data. Guidance, not a credit decision.


WHY YOU CAN TRUST IT

It never makes up a number. Fixed rules do the sums from your own payments, the AI only chooses what to look up and explains it, and every number is checked against your data before you see it. In our test of 65 questions with known answers it got all 65 right, in about two seconds each.


READY FOR S-MOBIILI

One card on the home screen: no new app, no new sign-in. The AI is an open model running in Finland, and a bank can run it on its own servers, so no payment data has to go to an AI provider.

See it in one minute: open the demo and press "Start the walkthrough".


FOR NVIDIA: NEMOTRON IS THE BRAIN OF THE PRODUCT

Every chat answer and every photo that is read is Nemotron's work, and it runs on our own GPU, not through someone else's API.

Model: NVIDIA Nemotron 3.5 Super VL (120B, the open NVFP4 weights), served by us with vLLM on one RTX PRO 6000.

What it does: it reads the question, chooses among 19 tools that can pull any figure out of two years of payments, and explains the result the way the bank teaches money. It is also the eyes: it reads the price from a photo of a price tag, and the account number, reference, amount and due date from a photo of a bill. One model for text, tools and vision.

Why it matters: a bank cannot send payments to someone else's API, and cannot ship a model that invents a number. Open weights solve the first. Tool use solves the second: Nemotron decides and explains, and never does arithmetic.

How we improved its outputs:

1. Tool descriptions in the customer's words, and tool errors that say how to fix the call.

2. A number check with one rewrite: fully traceable answers went from 94% to 100%.

3. An evaluation with known answers: right tool and arguments in 65 of 65, against 69% for a keyword baseline.

4. Reasoning off for tool selection: about 10 s to about 3 s an answer, then about 2 s on our own GPU.

5. Bills, measured in four rounds: what Nemotron reads is checked by check digits and a second reading. The first version offered 16 wrong drafts in 481 bills; the last offered none in 1,000 bills it had never seen (984 ready and right, 16 held back).

6. The bank's feedback, built the same day: after a "no" the tool returns when the purchase could fit, and Nemotron leads with it.

Full write-up:
https://github.com/codexpodextodex/money-mentor/blob/main/NVIDIA.md


FOR VERDA: WHAT MAKES IT SOMETHING A BANK COULD RUN

Verda's brief suggests keeping sensitive data in Europe by running an open model for a banking coach on infrastructure you control. That is this project, on three Verda products in Finland.

A confidential-computing GPU instance (RTX PRO 6000, encrypted memory) answers the public demo: a 120-billion-parameter model, healthy 10 minutes after we ordered the machine. Payments are in the prompt, so this is what a bank would ask for first.

A serverless container holds a second copy of the model that scales with demand.

A CPU instance hosts the app.

On the way, vLLM answered in junk on the confidential GPU while reporting healthy. We traced it to a known vLLM bug, reproduced it on Verda's machine without any model, confirmed a one-setting workaround, and wrote it up for Verda. The same 65 questions are all right on both hosts.

Process and scaling:
https://github.com/codexpodextodex/money-mentor/blob/main/VERDA.md


Made-up data, no real customer. S-Pankki's logo and typefaces are used with the bank's permission.
```

### Discord `#verda` (the required post; the link works once the repository is public)

Team Moonshot (table A78): Money Mentor, a banking coach for S-Pankki's challenge. NVIDIA Nemotron 3.5 Super VL (120B) runs on your confidential-computing RTX PRO 6000 in Finland, with a serverless container as the second host and the app on a CPU instance. Live: https://95-216-229-240.sslip.io

Summary of the process: https://github.com/codexpodextodex/money-mentor/blob/main/VERDA.md

One thing you may want for your docs: on the confidential machines vLLM 0.32 reports healthy and answers in junk. It is vllm#57224 (the V2 model runner reads stale input under GPU confidential computing). We reproduced it on your machine without a model, and `VLLM_USE_V2_MODEL_RUNNER=0` fixes it with confidential mode still on. The full report with the reproduction is in the repository: deploy/verda-confidential-gpu-report.md. Happy to walk anyone through it at booth 6.

### Discord `#nvidia` (optional)

Team Moonshot (table A78): Money Mentor, a money trainer for S-Pankki's mobile bank. Nemotron 3.5 Super VL is the coach: it picks among 19 tools over the customer's own payments, explains the result in Finnish, Swedish or English, and reads price tags from photos. It never does the arithmetic, and every number in an answer is checked against the data. It also turns a photographed bill into a payment draft: in a test of 1,000 bills no draft was offered with a wrong field. 65 of 65 evaluation questions right, median 2.3 s, self-hosted on one RTX PRO 6000. Live: https://95-216-229-240.sslip.io · How we used it: https://github.com/codexpodextodex/money-mentor/blob/main/NVIDIA.md

### Pitch in one breath

No Finnish bank lets you talk to your own money. Money Mentor does, and it teaches as it answers: essentials first, a buffer for the unexpected, and everyday spending is what is left. The model explains, the engine does the maths, and you can see the working behind every number.
