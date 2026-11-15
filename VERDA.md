# Money Mentor on Verda: a banking coach on a confidential GPU in Finland

Junction 2026 · Verda Compute Track, Best use of Verda · Team Moonshot

Verda's challenge page lists this idea: "Keep sensitive data in Europe. Run open-weight models for a banking coach or a recruitment tool on infrastructure you control, instead of sending data to someone else's API."

We built that sentence. Money Mentor is a money trainer for S-Pankki's mobile bank: a customer asks about their own money and gets an answer in about two seconds. The model behind it is NVIDIA Nemotron 3.5 Super VL, 120 billion parameters, and it runs on a Verda confidential-computing GPU in Finland. The app, the model and its standby copy are all on Verda.

Try it: https://95-216-229-240.sslip.io

## What runs where

| What | Verda product | Why this one | Price |
|---|---|---|---|
| The model, first host | GPU instance with confidential computing, `1RTXPRO6000.30V.CC`, Finland | The customer's payments are in the prompt, so the memory of the machine and of the GPU should be encrypted. This is what a bank would ask for first. | EUR 2.62 an hour |
| The model, second host | Serverless container, RTX PRO 6000, auto-scaling | An OpenAI-compatible endpoint with no server to look after. Replicas follow demand (payday peaks) and scale to zero. | $3.09 an hour |
| The app | CPU instance, `CPU.4V.16G`, Finland | The engine is SQL over 61 MB of Parquet and needs no GPU. | $0.05 an hour |

We looked at the Inference API first. Its model list did not include Nemotron when we checked, we had no key yet for the event's shared Nemotron endpoint, and a bank would need its own deployment anyway. So we hosted the model ourselves.

## Ambition: what compute made possible

- **The model does not fit on a laptop.** 75 GB of 4-bit weights need a 96 GB GPU. One RTX PRO 6000 is the smallest single card the model card lists.
- **Without our own compute there is no product.** A bank cannot send customers' payments to a third-party API. An open model on infrastructure it controls is what makes "chat with your own money" possible at all.
- **It is fast enough to be a conversation.** Median 2.3 seconds for a complete answer: the model picks tools, an engine computes from the customer's payments, the model explains, and every number is checked.
- **Confidential computing, in use.** Since midday on 14 November the public demo is answered by the confidential machine: memory encrypted with AMD SEV-SNP, GPU in confidential mode, HTTPS ending inside the machine.

## Fit: the path, as it happened

1. **Night, first try.** We ordered the confidential RTX PRO 6000 because it is the right story for a bank. It was running 36 seconds after the order and pulled 75 GB of weights in 2.5 minutes. vLLM loaded the model, reported healthy, and answered every request with one junk token repeated.
2. **Two hours of elimination, about EUR 4.** Not the model, not the 4-bit weights, not our flags: a small standard model failed the same way under vLLM, while plain PyTorch on the same GPU computed correctly.
3. **05:34, second try.** The same image and command as a serverless container on an ordinary RTX PRO 6000. Healthy in 12 minutes: correct answers, tool calls and image reading.
4. **06:15.** The app on a CPU instance, running 15 seconds after the order, public over HTTPS.
5. **Morning: the cause.** A known vLLM bug under GPU confidential computing ([vllm#57224](https://github.com/vllm-project/vllm/issues/57224)): the default model runner lets the GPU read each request through a mapped view of host memory, and on a confidential GPU that view goes stale, so the model runs correctly on old input. On a second confidential machine we reproduced the stale view **without any model**, then confirmed that one setting (`VLLM_USE_V2_MODEL_RUNNER=0`) fixes a small model and Nemotron, with confidential mode still on.
6. **11:29, in service.** A third confidential machine: 10 minutes from order to a healthy model. The public demo asks it first.

What we give back: [`deploy/verda-confidential-gpu-report.md`](deploy/verda-confidential-gpu-report.md), a report for Verda with a quick reproduction that needs only a small model, the workaround, the upstream fix to wait for, and four smaller notes from the weekend (a tutorial address that does not resolve, the default disk size against the vLLM image, the log API's 50 lines, and billing for shut-down machines). The failure is silent, the server says "healthy", and vLLM is what most people will start on these machines, so we think it is worth a line in the documentation.

## Working prototype

- **It runs:** https://95-216-229-240.sslip.io. Each answer shows which host wrote it under "How was this worked out?".
- **Same quality on both hosts:** 65 evaluation questions with known answers, asked of both hosts at the same time. All 65 right on both. Median 2.27 seconds on the confidential machine and 2.08 on the serverless container (`eval/results-verda-confidential.md`). Confidential computing cost us about 0.2 seconds an answer.
- **Failover, tested:** with the first host's address broken on purpose, the second host answered in 2.3 seconds when the address returned an error, and in 7.2 seconds for the first question when it did not answer at all.
- **Two hosts, used at once:** a 1,000-bill reading test ran on the serverless container while the public demo stayed on the confidential machine and stayed fast. The container answered 767 of the 1,000 itself and passed 233 on when it was busy.
- **Documented:** [`deploy/verda.md`](deploy/verda.md) has every command. `scripts/verda.py` runs the whole life cycle from the command line through Verda's API: instance types, availability, create, deploy a container, scale it, read its logs, check the balance, delete. `deploy/start_model.sh` sets the GPU ready and adds the workaround by itself on a confidential machine.

## Path to scale

- **The app and the model scale separately.** The engine is stateless SQL over Parquet. The model endpoint is OpenAI-compatible. The app asks three hosts in order and skips one that is down within 5 seconds.
- **Cost follows questions, not customers.** Only the chat calls the model. Safe to spend, the heads-up, the payday plan, the year replay and the home loan view are computed without it.
- **What an answer costs.** One request at a time, a EUR 2.62 GPU answers about 1,500 questions an hour at our median, which is under 0.2 cents an answer. vLLM batches requests, so real traffic should be cheaper. The nearest thing to a load test we have: with eight bill photos in flight at once (each is three model calls with a picture), a whole answer took a median of about 10 seconds against about 5 alone.
- **Peaks.** A bank's traffic peaks on payday. Serverless replicas follow the load and fall back to zero; one replica is configured for 16 requests at once.
- **Next steps for a real bank:** attestation of the confidential machine, the upstream vLLM fix once it is released, and more than one replica.

## What is not done

- We set the GPU's ready state by hand and did not run an attestation, so we have not proved to a third party what is running in the machine.
- Nobody has watched the confidential machine come back after a reboot.
- No real load test: apart from the eight-at-once bill run, the concurrency figures are settings, not measurements. In that run on the confidential GPU about 13 of 481 tool calls came back with garbled arguments; our checks caught them and asked again, and we did not find the cause.
- The demo's last fallback is NVIDIA's hosted API. A bank would leave that out.
