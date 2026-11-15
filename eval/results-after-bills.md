# Evaluation

Model: `nemotron-3.5-super-vl`. Held-out customers: CUST00246, CUST00483, CUST00572, CUST00573, CUST00594. Data as of 2026-09-30.

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| router | 65 | 69.2% | 61.5% | 58.5% | 100.0% | 20.0% | 0.01 s |
| model-minimal | 65 | 100.0% | 100.0% | 100.0% | 95.4% | 100.0% | 2.51 s |
| model-coach | 65 | 100.0% | 100.0% | 98.5% | 96.9% | 93.3% | 3.69 s |
| model-checked | 65 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 6.98 s |

Produced by `python scripts/evaluate.py`. Expected tools, arguments and numbers come from calling the engine directly.
