# Evaluation

Model: `nvidia/nemotron-3.5-super-vl-120b-a12b`. Held-out customers: CUST00026, CUST00063, CUST00076. Data as of 2026-09-30.

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| router | 39 | 69.2% | 61.5% | 53.8% | 100.0% | 0.0% | 0.01 s |
| model-minimal | 39 | 100.0% | 100.0% | 100.0% | 82.1% | 100.0% | 3.37 s |
| model-coach | 39 | 100.0% | 97.4% | 97.4% | 89.7% | 100.0% | 2.79 s |
| model-checked | 39 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 2.66 s |

Produced by `python scripts/evaluate.py`. Expected tools, arguments and numbers come from calling the engine directly.
