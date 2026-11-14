# Question for Astra: why does vLLM answer in junk on a confidential-computing GPU?

## What we want from you

On a Verda confidential-computing GPU machine, vLLM loads a model, reports healthy, and then answers every request with one junk token repeated. On an ordinary (non-confidential) machine with the same GPU model, the same image and the same command, it answers correctly.

Please tell us:

1. What you suspect the cause is, with your reasoning.
2. Whether you can find reports of the same thing online (vLLM, FlashInfer, flash-attn, Triton or PyTorch under NVIDIA GPU Confidential Computing, AMD SEV-SNP guests, or Blackwell RTX PRO 6000 / SM120 with driver 595). Links, please.
3. A short ordered list of experiments that would isolate it, cheapest first.
4. Any known workaround (flag, environment variable, different serving stack) that works in GPU confidential mode.

We are not blocked: the model runs on the ordinary machine. We want to understand this because a confidential machine is the better story for a bank.

## Short version of the evidence

| Machine | Software | Result |
|---|---|---|
| Confidential RTX PRO 6000 | vLLM 0.32.0 and 0.31.0, Nemotron 3.5 Super VL (NVFP4) | Loads, healthy, junk output |
| Confidential RTX PRO 6000 | vLLM 0.32.0, Qwen2.5-0.5B-Instruct (plain bf16) | Loads, healthy, junk output |
| Confidential RTX PRO 6000 | Plain PyTorch and `transformers`, same image, Qwen2.5-0.5B-Instruct | Correct: "The capital of Finland is Helsinki." |
| Ordinary RTX PRO 6000 (Verda serverless container) | vLLM 0.32.0, Nemotron 3.5 Super VL (NVFP4), same command | Correct answers, tool calls and image input |

So it is not the model, not the 4-bit weights and not our flags. It is vLLM's serving path on the confidential machine.

## The failing machine

- Verda instance type `1RTXPRO6000.30V.CC`, location FIN-03, OS image `24.04.cuda13.4.cc` ("Ubuntu 24.04 + CUDA 13.4 Open CC (driver 595)").
- Ubuntu 24.04.5 LTS, kernel 6.8.0-149-generic, 30 vCPU, 87 GB RAM.
- GPU: NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB, driver 595.91.07, compute capability 12.0.
- `dmesg`: "Memory Encryption Features active: AMD SEV SEV-ES SEV-SNP" and "software IO TLB: Memory encryption is active and system is using DMA bounce buffers".
- `nvidia-smi conf-compute -f`: "CC status: ON". `-e`: "CC Environment: PRODUCTION". `-d`: "DevTools Mode: OFF".
- `nvidia-smi conf-compute -grs` said "not-ready" after boot. Until we ran `nvidia-smi conf-compute -srs 1`, every CUDA call failed with "Error 802: system not yet initialized". After it, CUDA works. We did not run an attestation before setting the ready state.
- `nvidia-persistenced` was active; `nvidia-fabricmanager` was loaded but inactive.
- Docker 29.1.3 (Ubuntu's `docker.io`), NVIDIA Container Toolkit 1.20.1, containers started with `--gpus all --ipc=host` (also tried with `--privileged`).
- Images: `vllm/vllm-openai:v0.32.0` (torch 2.13.0+cu130) and `vllm/vllm-openai:v0.31.0`.

## What fails, exactly

All requests used temperature 0 unless noted, through `/v1/chat/completions`.

Nemotron (`nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`, snapshot `3acb0995`, all 92 large files verified against their SHA-256):

- "What is the capital of Finland? One word." with `max_tokens` 24 returns 24 tokens of one repeated junk token.
- Which junk token depends on the kernel used for the FP8 linear layers: with `FlashInferFP8ScaledMMLinearKernel` it is `ựu` repeated; with `PerTensorTorchFP8ScaledMMLinearKernel` it is `ähr` or `\x17` repeated.
- The output never reaches an end-of-sequence token: it always runs to `max_tokens`.
- With speculative decoding (MTP) on, the draft acceptance rate was 0.000.

Same result with every one of these:

- The model card's command for H200, the model card's command for GB200, and the vLLM recipe for this card (`recipes.vllm.ai`, `hardware=rtx_pro_6000`: `--trust-remote-code --max-model-len 16384 --max-num-seqs 128 --tensor-parallel-size 1 --speculative-config.method mtp --speculative-config.num_speculative_tokens 5 --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3`).
- Speculative decoding off.
- `--kv-cache-dtype bfloat16` (the attention backend then changed from FLASHINFER to FLASH_ATTN).
- `--moe-backend marlin` (log: "Your GPU does not have native support for FP4 computation ... Marlin kernel").
- `--kernel-config '{"linear_backend_per_quant":{"fp8_w8a8":"torch","nvfp4":"cutlass","nvfp4_w4a4":"cutlass"}}'` (log: "Using CutlassNvFp4LinearKernel for NVFP4 GEMM").
- vLLM 0.31.0 instead of 0.32.0.

Qwen/Qwen2.5-0.5B-Instruct on the same machine and image, "What is the capital of Finland? Answer in one short sentence.":

- Default settings: `[][][][][]...`
- `--enforce-eager` (attention backend FLASH_ATTN): `\xa0` repeated.
- `--attention-backend TRITON_ATTN`: `[][]` followed by newlines.

## What works on the same failing machine

Run inside the same `vllm/vllm-openai:v0.32.0` image, single process, `python3` directly:

- Matrix products on the GPU against a CPU reference: fp32 max relative error 8e-7, fp16 4.7e-4, bf16 3.5e-3, no NaN.
- Copies host to GPU and back, int64 and float32, pageable and pinned memory, blocking and `non_blocking=True`: all identical.
- Copy from GPU into pinned memory with `non_blocking=True`: identical.
- `vllm._custom_ops.rms_norm` against a manual reference: correct (0.3% in bf16).
- `torch.nn.functional.scaled_dot_product_attention` against a manual reference: correct.
- A hand-written Triton JIT kernel (a + b): exact.
- `torch.compile(torch.nn.Linear)`: exact.
- Embedding lookup: exact.
- `transformers` `AutoModelForCausalLM` with Qwen2.5-0.5B-Instruct in bf16, greedy `generate`: "The capital of Finland is Helsinki."

## Other things we saw there

- During start-up of the 0.32.0 image a FlashInfer JIT build failed: "[Flashinfer]: %globaltimer stamp kernel build failed ... fatal error: cusparse.h: No such file or directory". The server carried on. We do not know whether this also happens on the working machine.
- With `--gpu-memory-utilization 0.92` the FlashInfer autotuner logged "OOM detected, falling back to default tactic" many times (it asks for 4 GiB scratch buffers). At 0.88 this went away. The junk output was the same either way.
- With the GB200 command (`--async-scheduling` and MTP), the second request killed the engine: `AssertionError` at `vllm/v1/core/sched/async_scheduler.py`, line 71, `assert request.num_output_placeholders >= 0`. The first request had already returned junk.
- Log lines such as "Using FlashInferCutlassNvFp4LinearKernel for NVFP4 GEMM", "Using 'FLASHINFER_CUTLASS' NvFp4 MoE backend", "Using flashinfer Mamba SSU backend", "Warming up Mamba2 SSD Triton kernels".

## The working machine

- Verda serverless container, compute "RTX PRO 6000" x1 (not confidential), image `docker.io/vllm/vllm-openai:v0.32.0`, the same vLLM recipe arguments as above, weights downloaded from Hugging Face at start.
- Its log has a line mentioning SM12x, so it is the same GPU family.
- Healthy about 12 minutes after creation. "What is the capital of Finland? One word." returns "Helsinki". A tool-calling request returns the right tool call. A 32x32 green image is described as green. Our app's real questions take 1.6 to 2.2 seconds.
- We could not read its driver version or its kernel choices: the log API returns only the last 50 lines.

## What we did not test

- vLLM in a single process on the confidential machine (the offline `vllm.LLM(...)` class instead of the API server with its separate engine process).
- An ordinary (non-confidential) virtual machine with the same host image family, to separate "confidential mode" from "serverless platform differences".
- Another serving stack on the confidential machine (SGLang, llama.cpp, TGI).
- DevTools mode, or anything about attestation.
- Which first layer of the forward pass goes wrong (we did not dump intermediate activations).

## Our own guesses, unranked

- Something vLLM does that plain `transformers` does not, and that behaves differently when GPU memory and transfers are encrypted: the engine running in a separate process, CUDA streams or events with asynchronous transfers, its paged KV cache writes, or prebuilt kernels in flash-attn and FlashInfer.
- A driver issue specific to 595.91 in confidential mode on this GPU.
- A difference between the "CC" OS image and the ordinary ones (CUDA 13.4 on the host, cu130 in the container).

The same junk appearing with the Triton attention backend and with eager mode makes a single faulty kernel less likely to us, but we have not proved that.
