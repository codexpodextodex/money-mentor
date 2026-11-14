# Money Mentor

**Chat with your own money.** A personal economic trainer for a bank's mobile app, built at Junction 2026 for S-Pankki's challenge *Personal Economic Trainer*.

You ask in plain language ("How much did I spend on taxis last month?", "What is safe for me to spend this week?", "What if I cut dining out by 20%?"). An open model, NVIDIA Nemotron, decides what to look up and explains the result. It never does the arithmetic: every number comes from a deterministic engine over your own transactions, and every number in an answer is checked against that engine before you see it.

Team Moonshot: Felix Wickholm, Emil Rehn, Robin Wickholm.

## Run it

Python 3.11 or newer.

```bash
pip install -r requirements.txt
python run.py
```

Open http://localhost:8000. The first run downloads S-Pankki's dataset from GitHub (363 MB) and converts it to 61 MB of Parquet.

Without a model key the chat still works, through a built-in keyword router. To use Nemotron, copy `.env.example` to `.env` and add a key from https://build.nvidia.com (free, self-serve).

```bash
python -m pytest -q             # 141 tests
python scripts/evaluate.py      # accuracy table, see Evaluation below
```

## What it does

| Screen | What you get |
|---|---|
| Home | What is safe to spend this week, what stands out right now, the three baskets, month-by-month cash flow, what is safe to save |
| Ask | Chat with your money, or send a photo of a price tag, receipt or bill and ask "can I afford this?". A large purchase gets two honest answers, one if you need it and one if it is a treat, because the price alone cannot tell. Each answer shows the figures as a card, how many numbers were checked, and how it was worked out |
| Explore | Build your own view with taps (period, basket, category, break down by), drill in, or write SQL over your own rows |
| Replay | Your own last 12 months replayed with one habit changed: what would have been left, how many days below zero avoided, and your three biggest levers ranked |
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

- **The model never calculates.** It picks one of 16 tools and explains the result. Tools take no customer id: the server injects the signed-in customer, so the model cannot ask for anyone else's data.
- **Every number is checked.** After the model answers, each number in the text is looked up among the numbers the tools returned. A number found nowhere triggers one rewrite, and if it survives, the app shows a warning next to the answer.
- **MyData explore mode is safe by construction.** Free SQL runs in a separate in-memory database that holds only that customer's rows, with file and network access switched off, a row limit and a time limit. Safety does not depend on inspecting the query text.
- **It always works.** With no model, or when the model is unreachable, a keyword router answers the common questions from the same tools.
- **Small enough to run anywhere.** 3.6 million transactions load in under a second; a per-customer question takes a few milliseconds.

"Today" is 30 September 2026, the last day in the data (`MM_TODAY` overrides it).

## The model: NVIDIA Nemotron, in Europe

The app talks to any OpenAI-compatible endpoint, set in `.env`, and can ask two hosts in order:

- **Self-hosted on Verda, in Finland (asked first)**: the open weights (`nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`) served with vLLM in a Verda serverless container on one RTX PRO 6000. A bank's customer data and the model that reads it stay on infrastructure the bank controls. How it was set up, what it costs and what went wrong on the way is in `deploy/verda.md`.
- **NVIDIA's hosted API (fallback)**: `nvidia/nemotron-3.5-super-vl-120b-a12b`. Used when the Verda replica is asleep or starting.

Every answer records which host wrote it, and the app shows that under "How was this worked out?".

What Nemotron does here: it reads the question in Finnish, Swedish or English, chooses the tools and their arguments (often several at once), reads the JSON results, and explains them in the three-basket frame with one concrete next step. It also uses its vision: from a photo of a price tag, a receipt or a bill it reads the item and the price, and the engine checks that against what is safe to spend.

After adding a key, `python scripts/check_model.py` confirms that tool calling and image input work.

How we improved its output:

1. A coach prompt that fixes the division of labour (tools compute, the model explains) and the answer shape.
2. Tool descriptions written from the customer's words ("dining out" is the category Restaurants).
3. Tool errors that say how to fix the call, so the model corrects itself.
4. The number check with one rewrite.
5. An evaluation with known answers, below.

## Evaluation

`scripts/evaluate.py` asks 13 questions per held-out customer, in English, Finnish and Swedish. The right tool, arguments and number are known in advance, because the engine computes them directly. Results are written to `eval/results.md`.

Run on 14 Nov 2026 against the model we host on Verda, 65 questions per system (13 questions for each of 5 held-out customers):

| System | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish and Swedish right | Median time |
|---|---|---|---|---|---|---|
| Keyword router, no model (baseline) | 69% | 62% | 54% | 100% | 0% | 0.01 s |
| Nemotron, bare prompt, no number check | 100% | 100% | 100% | 91% | 100% | 2.2 s |
| Nemotron, coach prompt, no number check | 100% | 100% | 100% | 95% | 100% | 1.9 s |
| Nemotron, coach prompt and number check (what the app runs) | 100% | 100% | 98.5% | 100% | 100% | 1.9 s |

Nemotron chose the right tool and arguments every time. What the bare model gets wrong is not the lookup but the telling: in 6 answers of 65 it added a figure of its own (a rounded total, a percentage it worked out). The number check caught those: three answers were rewritten, and one of the rewrites dropped the figure the question asked for, which is the 98.5%. The sample is small, so read the percentages as a direction, not a benchmark. The raw rows are in `eval/results.json`.

An earlier run on the same day through NVIDIA's hosted API (3 customers, 39 questions, an earlier prompt) is kept in `eval/results-nvidia-api.md`: the same pattern, with a median of 2.7 seconds.

## Data

Synthetic data by S-Pankki for Junction 2026: https://github.com/hackjunction/Junction-2026-S-pankki. It is not included in this repository; `python scripts/fetch_data.py` downloads it. Demo personas are real customer ids from that dataset, picked by rules in `app/insights.py`.

## Licence

MIT, see `LICENSE`. All code was written at Junction 2026. `web/vendor/` holds third-party code under its own licence.
