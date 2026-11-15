# Money Mentor

**Your bank app shows a list of payments. Money Mentor tells you where you stand.** A money trainer inside S-mobiili, S-Pankki's mobile bank: ask anything about your own money, see what is safe to spend this week, get a heads-up before it runs out, and get a bill ready to pay by photographing it. Built at Junction 2026.

| | |
|---|---|
| Live demo | https://95-216-229-240.sslip.io. Press "Start the walkthrough": 13 steps, about a minute and a half. It works on a phone |
| Main challenge | S-Pankki: Personal Economic Trainer |
| Tech tracks | NVIDIA: Best Use of Nemotron ([NVIDIA.md](NVIDIA.md)) and Verda: Best use of Verda ([VERDA.md](VERDA.md)) |
| Team | Moonshot: Felix Wickholm, Emil Rehn, Robin Wickholm |
| Licence | MIT. All code was written at the event |

## The idea in five lines

1. The customer asks in their own words, in Finnish, Swedish or English, or sends a photo.
2. An open model, **NVIDIA Nemotron 3.5 Super VL**, decides what to look up and explains the result. It never does arithmetic.
3. A deterministic engine computes every figure from the customer's own payments.
4. Every number in an answer is traced back to the data before the customer sees it.
5. The model runs on a **Verda confidential-computing GPU in Finland**, and a bank could run the same open weights on its own servers, so payment data does not have to go to an AI provider.

## What was measured

Every figure below can be reproduced or read in the repository.

| What | Result | Where |
|---|---|---|
| Questions with known answers, full system | 65 of 65 right: tool, arguments, number, and every number traceable | `eval/results.md`, `python scripts/evaluate.py` |
| The same questions, keyword baseline without the model | Right tool for 69%, Finnish and Swedish right for 20% | `eval/results.md` |
| Answers with every number traceable, without and with the number check | 94%, then 100% | `eval/results.md` |
| Time for a whole answer | Median 2.3 seconds, on one RTX PRO 6000 | `eval/results.md` |
| Bills read from photos, 1,000 bills not seen during tuning | 984 right and ready to confirm, 16 held back for the customer to check, none offered with a wrong account number, reference, amount or due date | `eval/bill-reading.md`, `python scripts/bill_reading_test.py` |
| The same evaluation on both of our model hosts | All 65 right on both; 2.27 s median on the confidential GPU, 2.08 s on the serverless container | `eval/results-verda-confidential.md` |
| Automated tests | 229 | `python -m pytest -q` |

The samples are small and our own: read them as a direction, not a benchmark. What is not done is listed under [Limits](#limits).

## How it meets each challenge

### S-Pankki: Personal Economic Trainer

| Criterion | In Money Mentor |
|---|---|
| Impact on financial literacy | Every answer uses the bank's three baskets: essentials first, a buffer for the unexpected, and everyday spending is what is left. "Safe to spend this week" is one number built from them. The customer's own year is replayed with one habit changed |
| Originality of AI integration | The model never calculates and the app shows its working: the payments that were counted are ticked off, and each answer says how many numbers were checked. A price tag or a bill can be photographed |
| Clarity of the mobile user experience | It looks and reads like S-mobiili and leads with one number. A 13-step walkthrough shows it in a minute and a half |
| Feasibility | It is live. 65 of 65 test questions right, answers in about two seconds, 229 tests, an open model on a GPU in Finland |
| Potential to integrate into S-mobiili | A web app that embeds in the mobile app: one card on the home screen and a place in the Bank tab, no new sign-in, three languages |

On Saturday S-Pankki's team asked what the trainer says after a "no" to "can I afford this?". Since that evening it says when the purchase could fit: from the next payday, or by changing the one habit that mattered most in the customer's own year.

### NVIDIA: Best Use of Nemotron

| Criterion | In Money Mentor |
|---|---|
| Meaningful Nemotron usage | Nemotron 3.5 Super VL is the only model in the product. Every chat answer and every photo that is read is its work. Without it the keyword fallback gets 69% of the tools right |
| Technical execution | Tool calling over 19 tools, three model hosts asked in order with failover, a number check with one rewrite, guards for photos and follow-up questions, 229 tests |
| Quality of AI output | An evaluation with known answers (65 of 65), and a bill-reading test in four rounds that took wrong drafts from 16 in 481 bills to none in 1,000 unseen bills |
| Creativity and differentiation | The model reads and explains, arithmetic decides: check digits and a second reading verify what it read from a bill. One model does text, tools and vision, self-hosted from the open weights |

The full write-up is [NVIDIA.md](NVIDIA.md).

### Verda: Best use of Verda

| Criterion | In Money Mentor |
|---|---|
| Ambition | A 120-billion-parameter open model (75 GB of weights) answering a bank's customers in about two seconds. It does not fit on a laptop, and a bank cannot use a third-party API for this at all |
| Fit | Three Verda products, each for a reason: a confidential-computing GPU instance for the model (payments are in the prompt), a serverless container as the second host (it scales with demand), a CPU instance for the app |
| Working prototype | The public demo is answered by the confidential GPU. The path is documented command by command, including a vLLM bug on confidential GPUs that we traced, reproduced on Verda's machine and wrote up for Verda |
| Path to scale | The app and the model scale separately, only the chat calls the model (cost follows questions, not customers), and hosts fail over within five seconds |

The full write-up is [VERDA.md](VERDA.md). The commands are in [`deploy/verda.md`](deploy/verda.md) and the bug report in [`deploy/verda-confidential-gpu-report.md`](deploy/verda-confidential-gpu-report.md).

## Run it

Python 3.11 or newer.

```bash
pip install -r requirements.txt
python run.py
```

Open http://localhost:8000. The first run downloads S-Pankki's dataset from GitHub (363 MB) and converts it to 61 MB of Parquet.

Without a model key the chat still works, through a built-in keyword router. To use Nemotron, copy `.env.example` to `.env` and add a key from https://build.nvidia.com (free, self-serve).

```bash
python -m pytest -q             # 229 tests
python scripts/evaluate.py      # accuracy table, see Evaluation below
```

## What it does

| Screen | What you get |
|---|---|
| Home | What is safe to spend this week, what stands out right now, the three baskets, month-by-month cash flow, what is safe to save |
| Ask | Chat with your money, or send a photo of a price tag, receipt or bill and ask "can I afford this?". A large purchase gets two honest answers, one if you need it and one if it is a treat, because the price alone cannot tell. Each answer shows the figures as a card, how many numbers were checked, and how it was worked out |
| A bill, from a photo | Photograph a bill and the payment is prepared: payee, account number, reference, amount, due date. The engine recalculates the check digits and has the amount and the due date read twice, so a misread is caught, and you confirm. In a test of 1,000 bills no draft was offered with a wrong field (`eval/bill-reading.md`). In the demo nothing is paid |
| Explore | Build your own view with taps (period, basket, category, break down by), drill in, or write SQL over your own rows |
| Replay | Your own last 12 months replayed with one habit changed: what would have been left, how many days below zero avoided, and your three biggest levers ranked |
| Payday plan | A split of the next salary into the three baskets and savings, next to what the last pay period really looked like, to accept with one tap. With it, the weeks ahead: the balance day by day until the payday after next, and a heads-up if it would go below zero |
| Basket quiz | Six of your own payments to sort into the three baskets, with the rule behind each answer |
| Home loan | How ready you are for a mortgage, learned from 200 real application outcomes in the data |

### The three baskets

S-Pankki's teaching idea is that everyone's spending falls into three baskets. Money Mentor sorts every payment automatically and can tell you why.

| Basket | Meaning | Rule |
|---|---|---|
| 🏠 Regular essentials | Mandatory and regular | Housing, utility bills, groceries, transport (except taxis) |
| 🔧 Unexpected necessities | Mandatory but irregular | Health; Home & Tech or transport payments of EUR 300 or more (a repair or replacement) |
| ☕ Everyday spending | Your own choice, what slips through your fingers | Restaurants, entertainment, lifestyle, travel, taxis, smaller Home & Tech buys |

Investment deposits are savings and transfers to your own accounts are transfers; neither counts as spending. The rules are in `app/baskets.py`, in one readable SQL `CASE`.

### Safe to spend

The pay period is budgeted basket by basket, so the answer teaches the idea while it gives the number:

```
expected salary
- regular essentials     bills, plus groceries and transport at your usual pace
- unexpected buffer      your own 12-month monthly average, set aside
- savings goal           10% of salary by default (you can change it)
= everyday budget for this pay period
- everyday spending since payday
= safe to spend until the next payday
```

The result is capped by what the balance can cover once the bills due before payday are paid, so it never points into overdraft. "Safe to save" comes from the same figures.

A bill that comes once a month, such as the housing payment, is planned for every month at its usual amount and on its usual day, also after a month in which it was missed. In the data 84% of customers paid housing in all of the last six months, 8% in five and 3% in four.

### Payday plan and the weeks ahead

The same budget, turned into an action and into a look ahead (`app/plan.py`):

- **Payday plan.** Before the next salary arrives, the app proposes how to split it: regular essentials first, then the buffer for the unexpected, then savings (to Säästäjä, S-Pankki's own saving service), and everyday spending is what is left, per week and per day. When the salary does not stretch, everyday spending and savings give way first and the plan says so. Accepting is one tap. In this demo that only saves the plan: the assistant never moves money.
- **The weeks ahead.** The balance day by day until the payday after next, if the coming weeks go like the customer's usual ones: salary on its usual day, monthly bills on theirs, shopping at the pace of the last 90 days. If the balance would go below zero, the customer gets a heads-up before it happens, with the bill that comes first and the level of everyday spending that avoids it. In the data 13% of customers would get one today. It is the usual pattern projected forward, not a forecast, and the screen says so.

### Your year, replayed

Advice like "spend 20% less" is easy to give and hard to believe. So the trainer tests each habit on the customer's own history: it takes their real payments for the last 12 months, applies one rule, and replays the balance day by day. Five levers are tried and ranked by what they would have left on the account, so the one a customer sees first is the one that mattered most in their own year. For one demo customer the biggest lever is the handful of heavy weeks; for another it is the purchases under EUR 15.

Two limits are stated on the screen. It is arithmetic, not cause and effect: it assumes money not spent stayed on the account. And a lever that mattered last year may not matter next year, so each lever is also replayed on the year before. In a sample of 300 customers the top lever was the same in both years for 78%.

The code is in `app/replay.py`.

### Mortgage readiness

The dataset includes 200 mortgage applications (150 approved, 50 rejected) linked to transaction customers. From them the app learns what the bank looked at: the income the bank required was a fixed 1.84% of the loan per month, approved buyers typically put in 15% of their own money, and too little collateral was the most common reason for rejection. It then shows a customer four checks (income, own money, collateral, money habits), how far they are from a typical approval, and the changes that would matter most. It is guidance, never a credit decision.

## How it works

```
 phone browser (web/, no build step)
        |
   FastAPI  (app/server.py)
        |
   agent    (app/agent.py)  -- tools -->  engine (DuckDB SQL over Parquet)
        |                                   app/engine.py    spending, baskets, cash flow, safe to spend, what-if
   Nemotron 3.5 Super VL                    app/insights.py  spender type, comparison with peers
   (NVIDIA API, or self-hosted on Verda)    app/mortgage.py  mortgage readiness
        |                                   app/explore.py   free SQL in a per-customer sandbox
   number check (app/grounding.py)
```

Design decisions:

- **The model never calculates.** It picks among 19 tools and explains the result. Tools take no customer id: the server injects the signed-in customer, so the model cannot ask for anyone else's data.
- **Every number is checked.** After the model answers, each number in the text is looked up among the numbers the tools returned. A number found nowhere triggers one rewrite, and if it survives, the app shows a warning next to the answer.
- **MyData explore mode is safe by construction.** Free SQL runs in a separate in-memory database that holds only that customer's rows, with file and network access switched off, a row limit and a time limit. Safety does not depend on inspecting the query text.
- **It always works.** With no model, or when the model is unreachable, a keyword router answers the common questions from the same tools.
- **Small enough to run anywhere.** 3.6 million transactions load in under a second; a per-customer question takes a few milliseconds.

"Today" is 30 September 2026, the last day in the data (`MM_TODAY` overrides it).

## NVIDIA Nemotron: the model behind every answer

The model is NVIDIA Nemotron 3.5 Super VL, the open NVFP4 weights (`nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`), served by us with vLLM 0.32. It is the only model in the product.

What it does here:

- **Understands the question** in Finnish, Swedish or English.
- **Chooses the tools** and their arguments among 19, several at once when a question needs it (`app/tools.py`), and corrects a call when a tool says what was wrong with it.
- **Explains the result** in the bank's three-basket way of teaching, with one concrete next step.
- **Reads photos.** From a price tag it reads the item and the price, and the engine answers "can I afford this?". From a bill it reads the payee, the account number, the reference, the total and the due date, and the engine turns them into a payment draft.
- **Never calculates.** Every figure comes from the engine, and every number in an answer is checked against the tool results (`app/grounding.py`).

Why this model:

- **Open weights.** A bank cannot send customers' payments to somebody else's API. It can run these weights on its own servers.
- **One model for text, tools and vision.** One thing to host, test and audit, not three.
- **Fast enough for a conversation.** A complete tool-calling answer takes a median of 2.3 seconds on one RTX PRO 6000.
- **Tool calling that works as released.** With a bare prompt it already chose the right tool and arguments on all 65 evaluation questions, in three languages. Nothing was fine-tuned.

How its output was improved, each step measured:

1. Tool descriptions written in the customer's words, and tool errors that say how to fix the call.
2. A number check with one rewrite: answers with every number traceable went from 94% to 100%.
3. Reasoning switched off for tool selection: about 10 seconds an answer became about 3, then about 2 on our own GPU.
4. Guards found by testing: a photo answer must rest on a lookup, and a follow-up question gets a fresh lookup so its numbers can be checked.
5. Bill reading tested in four rounds on made-up bills: the first version offered 16 wrong drafts in 481 bills, the last none in 1,000 bills it had never seen.

After adding a key, `python scripts/check_model.py` confirms that tool calling and image input work. The details, the evaluation table and the limits are in [NVIDIA.md](NVIDIA.md).

## Verda: where it runs, and why there

A bank's customer data and the model that reads it have to stay on infrastructure the bank controls. So everything runs on Verda, in Finland, on three products:

| What | Verda product | Why this one |
|---|---|---|
| The model, asked first | GPU instance with confidential computing (RTX PRO 6000, AMD SEV-SNP, GPU in confidential mode) | The customer's payments are in the prompt, so the memory of the machine and of the GPU is encrypted. This is what a bank would ask for first |
| The model, asked second | Serverless container on an RTX PRO 6000 | An endpoint with no server to look after, which follows demand (payday peaks) and scales to zero |
| The app | CPU instance | The engine is SQL over 61 MB of Parquet and needs no GPU |

NVIDIA's hosted API is the last fallback in the demo; a bank would leave it out. A host that does not connect within five seconds is skipped, and every answer records which host wrote it: the app shows that under "How was this worked out?".

What happened on the way: on the confidential GPU, vLLM loaded the model, reported healthy and answered in junk. It is a known vLLM bug under GPU confidential computing. We reproduced the cause on Verda's machine without any model, confirmed a one-setting workaround for Nemotron, and wrote it up for Verda (`deploy/verda-confidential-gpu-report.md`). The same 65 evaluation questions are all right on both hosts.

What it would take to scale: the engine is stateless and the model endpoint is OpenAI-compatible, so they scale separately. Only the chat calls the model: safe to spend, the heads-up, the payday plan, the replay and the home loan view are computed without it, so cost follows the questions asked, not the number of customers.

The process, the prices and what is not done are in [VERDA.md](VERDA.md); every command is in [`deploy/verda.md`](deploy/verda.md).

## Evaluation

`scripts/evaluate.py` asks 13 questions per held-out customer, in English, Finnish and Swedish. The right tool, arguments and number are known in advance, because the engine computes them directly. Results are written to `eval/results.md`.

Run on 14 Nov 2026 against the model we host on Verda, 65 questions per system (13 questions for each of 5 held-out customers):

| System | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish and Swedish right | Median time |
|---|---|---|---|---|---|---|
| Keyword router, no model (baseline) | 69% | 62% | 58% | 100% | 20% | 0.01 s |
| Nemotron, bare prompt, no number check | 100% | 100% | 100% | 94% | 100% | 2.3 s |
| Nemotron, coach prompt, no number check | 100% | 100% | 100% | 94% | 100% | 2.2 s |
| Nemotron, coach prompt and number check (what the app runs) | 100% | 100% | 100% | 100% | 100% | 2.3 s |

Nemotron chose the right tool and arguments every time, among the 18 tools the app had then. With the nineteenth (the bill tool) a rerun was right on all 65 again (`eval/results-after-bills.md`). What the model gets wrong without the check is not the lookup but the telling: in 4 answers of 65 it added a figure of its own (a rounded total, a percentage it worked out). With the number check three answers were rewritten and all 65 ended with every number traceable. Each run draws five customers at random, so the figures move a little from run to run: an earlier run the same morning had one rewrite that dropped the figure the question asked for (98.5% in that column). The sample is small, so read the percentages as a direction, not a benchmark. The raw rows are in `eval/results.json`.

An earlier run on the same day through NVIDIA's hosted API (3 customers, 39 questions, an earlier prompt) is kept in `eval/results-nvidia-api.md`: the same pattern, with a median of 2.7 seconds.

## Limits

- The evaluations are our own and small: 65 questions for five customers, and 1,000 made-up bills. Nobody else has repeated them.
- The test bills are rendered pictures from one generator, not phone photos of paper. Nobody has tried a real bill. A payee's name has no check digit; it was copied exactly on 886 of the 1,000 drafts.
- Nothing is ever paid: a bill becomes a draft, and the plan is only saved. The assistant moves no money.
- The confidential machine has not been attested to a third party, and nobody has watched it come back after a reboot.
- No load test. With eight bill photos in flight at once an answer took about 10 seconds instead of 5.
- The model is used as released: nothing was fine-tuned.
- The data is synthetic, and the demo's "today" is 30 September 2026, the last day in it.

## Data

Synthetic data by S-Pankki for Junction 2026: https://github.com/hackjunction/Junction-2026-S-pankki. It is not included in this repository; `python scripts/fetch_data.py` downloads it. Demo personas are real customer ids from that dataset, picked by rules in `app/insights.py`.

## Licence

MIT, see `LICENSE`. All code was written at Junction 2026. `web/vendor/` holds third-party code under its own licence.
