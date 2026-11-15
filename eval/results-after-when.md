# Evaluation

Model: `nemotron-3.5-super-vl`. Held-out customers: CUST00246, CUST00483, CUST00572, CUST00573, CUST00594. Data as of 2026-09-30.

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| router | 65 | 69.2% | 61.5% | 58.5% | 100.0% | 20.0% | 0.01 s |
| model-minimal | 65 | 100.0% | 100.0% | 100.0% | 98.5% | 100.0% | 2.28 s |
| model-coach | 65 | 100.0% | 100.0% | 98.5% | 98.5% | 93.3% | 2.24 s |
| model-checked | 65 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 2.59 s |

Produced by `python scripts/evaluate.py`. Expected tools, arguments and numbers come from calling the engine directly.
