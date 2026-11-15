# Evaluation: Verda's confidential-computing GPU against the serverless container

The same 65 questions on both hosts, run at the same time on 14 Nov 2026 from a laptop at the venue. Customers: CUST00246, CUST00483, CUST00572, CUST00573, CUST00594 (the five of `eval/results.md`). Data as of 2026-09-30. Every answer in each run was written by the host named: no fallback happened.

Both hosts serve `nemotron-3.5-super-vl` (NVIDIA's NVFP4 weights) with vLLM 0.32.0 and the same arguments on one RTX PRO 6000 in Finland.

- **Confidential**: a `1RTXPRO6000.30V.CC` machine (AMD SEV-SNP, GPU confidential mode on), vLLM started with `VLLM_USE_V2_MODEL_RUNNER=0`, reached over HTTPS.
- **Serverless**: a Verda serverless container on an ordinary RTX PRO 6000.

## Confidential-computing machine

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| model-minimal | 65 | 100.0% | 100.0% | 100.0% | 96.9% | 100.0% | 2.31 s |
| model-coach | 65 | 100.0% | 100.0% | 98.5% | 98.5% | 93.3% | 2.18 s |
| model-checked | 65 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 2.27 s |

## Serverless container

| System | Questions | Right tool | Right arguments | Right number in answer | Every number traceable | Finnish/Swedish right | Median time |
|---|---|---|---|---|---|---|---|
| model-minimal | 65 | 100.0% | 100.0% | 100.0% | 90.8% | 100.0% | 2.07 s |
| model-coach | 65 | 100.0% | 100.0% | 100.0% | 96.9% | 100.0% | 2.0 s |
| model-checked | 65 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 2.08 s |

Produced by `python scripts/evaluate.py --ids CUST00246 CUST00483 CUST00572 CUST00573 CUST00594 --systems model-minimal model-coach model-checked --name <name>`, once with only the confidential host switched on and once with only the serverless one.

## Reading it

- The full system (`model-checked`, with the number check) is right on all 65 questions on both hosts.
- The confidential machine is about 0.2 seconds slower per answer: median 2.27 s against 2.08 s, mean 2.50 s against 2.22 s, nine answers in ten under 3.24 s against 2.91 s.
- The one answer scored wrong on the confidential machine (`model-coach`, "Paljonko käytin ruokaostoksiin viime kuussa?") is a correct answer. The customer spent nothing on groceries in August 2026 and the model said so ("ruokaostoksiin ei tullut menoja"); the scorer did not recognise that wording as zero. The scorer's list now includes it.
- The differences in the other columns are the size of the run-to-run variation we see on one host: the model answers at temperature 0.2.

## The price-tag photo, six times in each language on each host

| Question | Confidential: says what it read | Serverless: says what it read | Median time, confidential / serverless |
|---|---|---|---|
| "Can I afford this?" | 6 of 6 | 6 of 6 | 3.0 s / 2.6 s |
| "Onko minulla varaa tähän?" | 2 of 6 | 1 of 6 | 3.8 s / 3.5 s |
| "Har jag råd med det här?" | 4 of 6 | 1 of 6 | 3.2 s / 2.9 s |

"Says what it read" means the answer opens with the item and price read from the photo. In Finnish and Swedish the model often left that line out, on both hosts: a weakness of the app's prompt in those languages, not of either host.

Fixed the same day: the app now writes that line itself, from what the model passed to the tool, and asks once for the customer's language when a Finnish price tag pulls an answer to an English question into Finnish. After the fix, the same question six times for each of two customers in each language (36 answers per host):

| | Confidential | Serverless |
|---|---|---|
| Opens with what was read, once | 36 of 36 | 36 of 36 |
| Names the product as written on the tag | 36 of 36 | 36 of 36 |
| Answer in the language of the question | 36 of 36 | 36 of 36 |
| Median time | 2.8 to 3.5 s | 2.5 to 3.3 s |

## An earlier run on a first confidential machine

On a first machine the same morning, with five other customers, `model-checked` scored 63 of 65. Both misses were the same zero-in-Finnish wording as above, so on reading it was 65 of 65. Median 2.08 s.
