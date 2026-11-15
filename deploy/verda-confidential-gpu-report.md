# Report to Verda: vLLM answers in junk on the confidential-computing RTX PRO 6000, and how to make it work

From team Moonshot, Junction 2026 (table A78). Written 14 November 2026.

## Summary

On a Verda confidential-computing GPU machine, vLLM loads a model, reports healthy, and then answers every request with one junk token repeated until `max_tokens`. In the same container on the same machine, plain PyTorch and `transformers` give correct results. The same vLLM image and command on a Verda serverless RTX PRO 6000 container works.

The cause is a known vLLM bug under GPU confidential computing. We reproduced it on Verda's machine and confirmed the workaround there:

**Start the vLLM container with `-e VLLM_USE_V2_MODEL_RUNNER=0`.** With that one change, and confidential mode still on, NVIDIA Nemotron 3.5 Super VL answers correctly on `1RTXPRO6000.30V.CC`: text, tool calls and image input. Our public demo now runs on it.

| Where | Software | Result |
|---|---|---|
| Confidential RTX PRO 6000 instance | vLLM 0.32.0 and 0.31.0, Nemotron 3.5 Super VL (NVFP4) | Loads, healthy, junk output |
| Confidential RTX PRO 6000 instance | vLLM 0.32.0, Qwen2.5-0.5B-Instruct (plain bf16) | Loads, healthy, junk output |
| Confidential RTX PRO 6000 instance | Plain PyTorch and `transformers`, same image, Qwen2.5-0.5B-Instruct | Correct: "The capital of Finland is Helsinki." |
| Serverless container, RTX PRO 6000 x1 | vLLM 0.32.0, Nemotron 3.5 Super VL (NVFP4), same arguments | Correct answers, tool calls and image input |

So it is not the model, not the 4-bit weights and not our flags. It is something in vLLM's serving path on that machine.

## The cause: vLLM's V2 model runner reads stale input under confidential computing

vLLM issue [#57224](https://github.com/vllm-project/vllm/issues/57224), "Silent garbage output on GPUs in Confidential Computing mode: V2 model runner's UVA views of pinned host memory are stale under CC", describes what we saw:

- The server reports healthy and `Qwen/Qwen2.5-0.5B-Instruct` answers `!!!!!!!!` or `[][][][]`, while plain `transformers` is correct on the same GPU.
- The original report is on the same driver, 595.91.07 (an H100 in an Intel TDX guest). Another reporter in the thread is on AMD SEV-SNP, like Verda's machine.
- The cause given there: the V2 runner hands the GPU a mapped view of host memory (UVA) instead of copying the request's inputs. Under confidential computing that view does not show what the CPU writes later, so the model runs every layer correctly on old token ids. Explicit copies are fine, which is why all our copy tests passed.
- That also fits two things we could not explain: changing the attention backend or the kernels made no difference, and the scheduler assertion we hit (`num_output_placeholders >= 0`) is reported there only with the V2 runner ([#57562](https://github.com/vllm-project/vllm/issues/57562)).

**Workaround reported there:** start vLLM with the environment variable `VLLM_USE_V2_MODEL_RUNNER=0`, which selects the older runner. Confidential computing stays on.

**Fix:** [PR #59981](https://github.com/vllm-project/vllm/pull/59981), merged on 9 November 2026. vLLM then detects confidential mode and uses explicit copies. It is not in 0.32.0 or 0.31.0, the versions we ran.

## Confirmed on Verda's machine, 14 November 2026

A second `1RTXPRO6000.30V.CC` instance (id `2387674f-206a-42d9-bfb9-2bf19908ac7a`, FIN-03, same image and driver), image `vllm/vllm-openai:v0.32.0`, GPU confidential mode on throughout.

**1. The stale view, without any model.** The same steps as `UvaBuffer` in `vllm/v1/worker/gpu/buffer_utils.py`: a CPU tensor created with `pin_memory=True`, mapped with `get_accelerator_view_from_cpu_tensor`, then written by the CPU.

```text
is_uva_available(): True
pin_memory=True tensor reports is_pinned(): False
initial          cpu: [1, 2, 3, 4, 5, 6, 7, 8]  gpu view: [1, 2, 3, 4, 5, 6, 7, 8]
after host write cpu: [99, 99, 99, 99, 99, 99, 99, 99]  gpu view: [1, 2, 3, 4, 5, 6, 7, 8]
explicit H2D copy       : [99, 99, 99, 99, 99, 99, 99, 99]
```

The GPU keeps reading the old values through the mapped view. An explicit copy delivers the new ones.

**2. Qwen2.5-0.5B-Instruct, one change between the two runs.** Default settings, two questions at temperature 0.

| Started with | Log | "What is the capital of Finland? Answer in one short sentence." | "Name three Finnish cities, comma separated." |
|---|---|---|---|
| nothing extra | "Using V2 Model Runner" | `[][][][][][]...` to `max_tokens` | `111111111111...` to `max_tokens` |
| `-e VLLM_USE_V2_MODEL_RUNNER=0` | no such line | "The capital of Finland is Helsinki." | "Helsinki, Turku, Oulu" |

**3. Nemotron 3.5 Super VL (NVFP4) with the switch.** The vLLM recipe for this card, unchanged, plus `-e VLLM_USE_V2_MODEL_RUNNER=0`:

```bash
nvidia-smi conf-compute -srs 1
docker run -d --name nemotron --gpus all --ipc=host -p 127.0.0.1:8001:8000 \
  -v /root/hf:/root/.cache/huggingface -e HF_HUB_OFFLINE=1 \
  -e VLLM_USE_V2_MODEL_RUNNER=0 \
  vllm/vllm-openai:v0.32.0 \
  nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4 \
  --served-model-name nemotron-3.5-super-vl \
  --trust-remote-code --max-model-len 16384 --max-num-seqs 128 --tensor-parallel-size 1 \
  --speculative-config.method mtp --speculative-config.num_speculative_tokens 5 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3
```

- Healthy 5 minutes 26 seconds after the container started, with the weights already on disk.
- "What is the capital of Finland? One word." returns "Helsinki" and stops.
- A tool-calling request returns `get_spending {"period": "last month", "subcategory": "taxis"}`.
- A 32x32 green image is described as "Green".
- Repeated requests with speculative decoding on did not crash the server.

**4. The control, on the same machine and the same boot.** The same command without the switch logs "Using V2 Model Runner" and answers the same four requests with `ựuựuựu...` and `ährährähr...` up to `max_tokens`: the same junk as on the first instance. Started again with the switch, it answers "Helsinki" again.

**5. Our app's own evaluation, the same questions on both hosts at the same time.** 65 questions with known answers for five customers, in English, Finnish and Swedish, each asked three ways (195 answers and about 400 requests per host). This ran on a third instance (id `b43552f2-fe28-4e0a-94e6-8dbd0365e07e`), reached over HTTPS. The figures are for the full system, the one with the number check:

| | Confidential machine | Serverless container |
|---|---|---|
| Right tool and right arguments | 65 of 65 | 65 of 65 |
| Right number in the answer | 65 of 65 | 65 of 65 |
| Every number traceable to the data | 65 of 65 | 65 of 65 |
| Median time per answer | 2.27 s | 2.08 s |
| Nine answers in ten under | 3.24 s | 2.91 s |

So for our workload the older runner on the confidential machine gives the same answers and costs about 0.2 seconds per answer. Details in `eval/results-verda-confidential.md`.

**6. In use.** Since midday on 14 November our public demo (https://95-216-229-240.sslip.io) asks the confidential machine first, with the serverless container as the second host. From ordering the machine to a healthy model took 10 minutes: Docker and the 33 GB image, 70 GB of weights in 3 minutes, and 5.5 minutes for vLLM to load.

**What is still open:**

- We did not test the upstream fix itself, only the workaround.
- We set the GPU's ready state by hand and did not run an attestation.

## The machine

This section and the three after it describe the first instance, before we knew the cause.

- Instance type `1RTXPRO6000.30V.CC`, location FIN-03, OS image `24.04.cuda13.4.cc`.
- Instance id `47716c4d-f95e-463a-a575-a9a52d1843cf`, hostname `money-mentor`. It ran for about two hours in the night between 13 and 14 November 2026 and is now deleted.
- Ubuntu 24.04.5 LTS, kernel 6.8.0-149-generic, 30 vCPU, 87 GB RAM.
- GPU: NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB, driver 595.91.07, compute capability 12.0.
- `dmesg`: "Memory Encryption Features active: AMD SEV SEV-ES SEV-SNP" and "software IO TLB: Memory encryption is active and system is using DMA bounce buffers".
- `nvidia-smi conf-compute -f`: "CC status: ON". `-e`: "CC Environment: PRODUCTION". `-d`: "DevTools Mode: OFF".
- Docker 29.1.3 (Ubuntu's `docker.io`), NVIDIA Container Toolkit 1.20.1. Containers were started with `--gpus all --ipc=host`; we also tried `--privileged`.
- Images: `vllm/vllm-openai:v0.32.0` (torch 2.13.0+cu130) and `vllm/vllm-openai:v0.31.0`.

## First thing we hit: the GPU is "not-ready" after boot

After boot `nvidia-smi conf-compute -grs` said "not-ready", and every CUDA call failed with "Error 802: system not yet initialized". After `nvidia-smi conf-compute -srs 1` CUDA worked. We did not run an attestation before setting the ready state.

Question: is setting the ready state by hand the intended step on this image, or should something have done it for us?

## What fails

All requests went through `/v1/chat/completions` at temperature 0.

**Nemotron** (`nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`, all 92 large files verified against their SHA-256):

- "What is the capital of Finland? One word." with `max_tokens` 24 returns 24 copies of one junk token. It never reaches an end-of-sequence token.
- Which junk token depends on the kernel used for the FP8 linear layers: `ựu` with `FlashInferFP8ScaledMMLinearKernel`; `ähr` or `\x17` with `PerTensorTorchFP8ScaledMMLinearKernel`.
- With speculative decoding (MTP) on, the draft acceptance rate was 0.000.

The result was the same with each of these:

- The model card's command for H200, the model card's command for GB200, and the vLLM recipe for this card (`recipes.vllm.ai`, `hardware=rtx_pro_6000`).
- Speculative decoding off.
- `--kv-cache-dtype bfloat16` (the attention backend then changed from FLASHINFER to FLASH_ATTN).
- `--moe-backend marlin`.
- `--kernel-config '{"linear_backend_per_quant":{"fp8_w8a8":"torch","nvfp4":"cutlass","nvfp4_w4a4":"cutlass"}}'`.
- vLLM 0.31.0 instead of 0.32.0.

**Qwen/Qwen2.5-0.5B-Instruct**, same machine and image, "What is the capital of Finland? Answer in one short sentence.":

- Default settings: `[][][][][]...`
- `--enforce-eager` (attention backend FLASH_ATTN): `\xa0` repeated.
- `--attention-backend TRITON_ATTN`: `[][]` followed by newlines.

This small model is the quickest way to reproduce it: start the confidential machine, set the ready state, serve `Qwen/Qwen2.5-0.5B-Instruct` with `vllm/vllm-openai:v0.32.0` on default settings, and ask it one question.

## What works on the same machine

Run with `python3` directly, in one process, inside the same `vllm/vllm-openai:v0.32.0` image:

- Matrix products on the GPU against a CPU reference: fp32 max relative error 8e-7, fp16 4.7e-4, bf16 3.5e-3, no NaN.
- Copies from host to GPU and back, int64 and float32, pageable and pinned memory, blocking and `non_blocking=True`: all identical.
- `vllm._custom_ops.rms_norm` and `torch.nn.functional.scaled_dot_product_attention` against manual references: correct.
- A hand-written Triton kernel, `torch.compile(torch.nn.Linear)` and an embedding lookup: exact.
- `transformers` `AutoModelForCausalLM` with Qwen2.5-0.5B-Instruct in bf16, greedy `generate`: "The capital of Finland is Helsinki."

## Other things in the logs

- While the 0.32.0 image started, a FlashInfer JIT build failed: "[Flashinfer]: %globaltimer stamp kernel build failed ... fatal error: cusparse.h: No such file or directory". The server carried on. We do not know whether this also happens on the working container.
- With the GB200 command (`--async-scheduling` and MTP) the second request killed the engine: `AssertionError` in `vllm/v1/core/sched/async_scheduler.py`, `assert request.num_output_placeholders >= 0`. The first request had already returned junk.

## What works: the serverless container

- Compute "RTX PRO 6000" x1, not confidential, image `docker.io/vllm/vllm-openai:v0.32.0`, start arguments from the vLLM recipe: `--trust-remote-code --max-model-len 16384 --max-num-seqs 128 --tensor-parallel-size 1 --speculative-config.method mtp --speculative-config.num_speculative_tokens 5 --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3`.
- Healthy about 12 minutes after creation, with 75 GB of weights downloaded at start.
- Our app's questions take 1.6 to 2.2 seconds for text and 2.3 to 5.6 seconds with a photo. NVIDIA's hosted API took 2.3 to 3.4 and about 5 seconds for the same questions.

## What we did not test

- vLLM in a single process on the confidential machine (the offline `vllm.LLM(...)` class instead of the API server with its separate engine process).
- An ordinary RTX PRO 6000 virtual machine, to separate "confidential mode" from "differences between an instance and a serverless container".
- Another serving stack on the confidential machine (SGLang, llama.cpp, TGI).
- DevTools mode, or anything about attestation.
- Which layer of the forward pass first goes wrong.

## Our guesses before we found the bug report, unranked

- Something vLLM does that plain `transformers` does not, and that behaves differently when GPU memory and transfers are encrypted: the engine in a separate process, CUDA streams or events with asynchronous transfers, the paged KV cache, or prebuilt kernels in flash-attn and FlashInfer.
- A driver issue specific to 595.91 in confidential mode on this GPU.
- A difference between the "CC" OS image and the ordinary ones (CUDA 13.4 on the host, cu130 in the container).

The same junk with the Triton attention backend and in eager mode makes one faulty kernel less likely to us, but we have not proved that.

## Questions for Verda

1. Did you know about this vLLM bug? It may be worth a line in the documentation for the confidential machines, since vLLM is what most people will start there, and the failure is silent: the server reports healthy.
2. Should the GPU's ready state be set by hand, and should attestation come first? What is the intended attestation flow on this image?
3. Is the `is_pinned()` result (false for pinned memory under confidential computing) expected from the driver?

## Smaller notes

- The confidential image comes without Docker, and the default 50 GB disk is filled by the vLLM image alone (33 GB). Enlarging the disk to 200 GB through the API worked on the running machine, with no reboot.
- The address `containers.verda.com` in the serverless tutorial did not resolve for us. `containers.datacrunch.io` works.
- The log API for a container deployment returned only the last 50 lines, so we could not read the driver version or vLLM's kernel choices on the working container.
- A shut-down instance is still charged in full. We only noticed because we checked the balance.
