# Evaluation

Model: `nemotron-3.5-super-vl`. Held-out customers: CUST00046, CUST00052, CUST00092, CUST00225, CUST00473. Data as of 2026-09-30.

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| router | 65 | 69.2% | 61.5% | 53.8% | 100.0% | 0.0% | 0.01 s |
| model-minimal | 65 | 100.0% | 100.0% | 100.0% | 90.8% | 100.0% | 2.16 s |
| model-coach | 65 | 100.0% | 100.0% | 100.0% | 95.4% | 100.0% | 1.91 s |
| model-checked | 65 | 100.0% | 100.0% | 98.5% | 100.0% | 100.0% | 1.87 s |

Produced by `python scripts/evaluate.py`. Expected tools, arguments and numbers come from calling the engine directly.
