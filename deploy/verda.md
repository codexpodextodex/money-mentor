# Running on Verda

Two parts, both on Verda's infrastructure in Finland: the model, and the app.

**Status on 14 Nov 2026, morning: the model and the app both run on Verda.** Nemotron 3.5 Super VL is served by vLLM in a Verda serverless container on one ordinary RTX PRO 6000, and the app asks it first, with NVIDIA's hosted API as the fallback. The app is on a small Verda CPU machine at https://95-216-229-240.sslip.io. A first attempt on a confidential-computing machine failed; all three are described below.

| What | Verda product | Price | Started |
|---|---|---|---|
| The model | Serverless container `money-mentor-nemotron`, RTX PRO 6000 x1, 1 replica | $3.09 an hour | 14 Nov, 05:34 |
| The app | Instance `money-mentor-app`, `CPU.4V.16G`, FIN-01, Ubuntu 24.04 | $0.048 an hour | 14 Nov, 06:15 |

Both keep charging until they are deleted:

```bash
python scripts/verda.py delete-deployment money-mentor-nemotron
python scripts/verda.py instances          # shows the id of money-mentor-app
python scripts/verda.py action <id> delete
```

## The app on a CPU machine

`python scripts/verda.py create money-mentor-app CPU.4V.16G ubuntu-24.04 FIN-01 <ssh-key-id>` started it; it was running 15 seconds later. Then, from the project folder:

1. The project was copied over with `tar` through `ssh` (code, `web/` with the brand files, the 61 MB of Parquet).
2. A `.env` with the model settings was written on the server, readable by root only: the Verda model address and inference key, and the NVIDIA host as the fallback. The Verda cloud credentials are not on the server.
3. `deploy/start_app.sh` installed the app as a systemd service on 127.0.0.1:8000 and put Caddy in front. Caddy gets the certificate by itself; with no domain of our own, `sslip.io` turns the address 95.216.229.240 into the name `95-216-229-240.sslip.io`. Every response carries `X-Robots-Tag: noindex`.

After a change on the laptop: `deploy/push_app.sh 95.216.229.240` copies the project again and restarts the app.

Checked from outside on 14 Nov 2026: the pages and brand files load over HTTPS, a chat question was answered by the Verda model in 1.4 seconds, and the Finnish walkthrough ran through the fast-food question (1.2 seconds) and the price-tag photo (3.2 seconds).

## What runs now: a serverless container

Created with `python scripts/verda.py deploy-model money-mentor-nemotron "RTX PRO 6000"`, which sends this to Verda's API:

| Setting | Value |
|---|---|
| Compute | RTX PRO 6000, 1 GPU (96 GB), not spot. $3.09 per hour, billed in 10-minute steps |
| Image | `docker.io/vllm/vllm-openai:v0.32.0`, port 8000, health check `/health` |
| Start command | the vLLM recipe for this card: `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4 --served-model-name nemotron-3.5-super-vl --trust-remote-code --max-model-len 16384 --max-num-seqs 128 --tensor-parallel-size 1 --speculative-config.method mtp --speculative-config.num_speculative_tokens 5 --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser nemotron_v3` |
| Volumes | scratch at `/root/.cache/huggingface` (the 75 GB of weights are downloaded at start), 16 GB memory volume at `/dev/shm` |
| Scaling | 1 to 1 replicas while we test; 16 concurrent requests per replica |

Measured on 14 Nov 2026:

- Healthy about 12 minutes after creation (image, 75 GB of weights, load, compile, warm-up).
- `python scripts/probe_endpoint.py <endpoint>/v1`: three sane answers out of three.
- `python scripts/check_model.py`: tool calling and image input both pass, each in 1.8 seconds.
- The app's own questions: 1.6 to 2.2 seconds for text, 2.3 to 5.6 seconds with the price-tag photo. NVIDIA's hosted API took 2.3 to 3.4 and about 5 seconds for the same questions.
- The app's requests use 5,200 to 8,400 of the 16,384 tokens of context.

The endpoint is `https://containers.datacrunch.io/money-mentor-nemotron/v1` (the address `containers.verda.com` in Verda's tutorial did not resolve for us). It needs an inference API key: Verda console, Credentials, Inference API Keys.

In `.env`:

```
VERDA_INFERENCE_KEY=<the inference key>
VERDA_LLM_BASE_URL=https://containers.datacrunch.io/money-mentor-nemotron/v1
MM_MODEL_HOST=verda
```

With `MM_MODEL_HOST=verda` the app asks the Verda model first and gives it 30 seconds. If it does not answer (asleep, starting, or the request is too long for its context), the app asks the `LLM_*` host instead and leaves Verda alone for two minutes. Every answer records which host wrote it (`served_by`), and the app shows it under "How was this worked out?".

To stop the charge: `python scripts/verda.py delete-deployment money-mentor-nemotron`. To start again: the `deploy-model` command above, then wait about 12 minutes.

## What happened on the confidential-computing machine

We started the only suitable single-GPU machine that was free: `1RTXPRO6000.30V.CC` in FIN-03, an RTX PRO 6000 (96 GB) with confidential computing (AMD SEV-SNP, GPU confidential mode on), image `24.04.cuda13.4.cc`. It ran for about two hours and cost about EUR 4.

What worked:

- The machine was running 36 seconds after the order.
- The 75 GB of weights downloaded from Hugging Face in 2.5 minutes, and all 92 large files match their SHA-256.
- The GPU has to be switched to its ready state after each boot, or every CUDA call fails with "Error 802: system not yet initialized": `nvidia-smi conf-compute -srs 1`.
- Plain PyTorch computes correctly on this machine: matrix products in fp32, fp16 and bf16, memory copies in both directions (pinned or not, blocking or not), a Triton kernel, `torch.compile`, and a small model (Qwen2.5-0.5B) through plain `transformers` answers "The capital of Finland is Helsinki."

What did not work:

- vLLM (`v0.32.0` and `v0.31.0`) loads Nemotron and reports healthy, but every answer is one repeated junk token. This is the same with the model card's H200 and GB200 commands, with vLLM's own recipe for this card, with speculative decoding off, with a bf16 attention cache, and with other kernels for the 4-bit layers (Marlin for the expert layers, vLLM's CUTLASS for the linear layers, torch for the FP8 layers).
- The same vLLM image gives junk for the small Qwen model too, also with `--enforce-eager` and with the Triton attention backend. So the fault is not Nemotron, the 4-bit weights or our settings: it is vLLM's serving path on this machine. We did not find which part.
- Separately, with speculative decoding on, the second request killed the server with an assertion in `async_scheduler.py` (`num_output_placeholders >= 0`).

What we do not know: whether the cause is the confidential mode or this GPU model, because no ordinary RTX PRO 6000 was free to compare.

Billing note: on Verda a shut-down machine is still charged in full. Only deleting it stops the charge. We deleted the machine through the API without naming its disk; the disk was listed as attached for a few minutes and was gone from the account half an hour later, so do not count on a disk surviving a delete.

The rest of this file is the plan as checked against Verda's and NVIDIA's documentation.

## What we checked

| Fact | Source |
|---|---|
| The model is `nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4`: open weights (OpenMDW-1.1, commercial use allowed), not gated, 75 GB in 88 files | Hugging Face model card and API |
| Supported single-GPU hardware: 1x RTX PRO 6000 (96 GB) or 1x H200 (141 GB), with vLLM `v0.32.0` | Model card, deployment table |
| The model card gives a full vLLM command for 1x H200. For the RTX PRO 6000 it lists the hardware but no command | Model card |
| Reasoning is switched off per request with `chat_template_kwargs: {"enable_thinking": false}` (not `reasoning_effort`) | Model card |
| Serverless container prices per GPU-hour: RTX PRO 6000 $3.09, H100 $5.71, H200 $7.30. Billed in 10-minute steps, scales to zero | verda.com/serverless-containers |
| Verda's own hosted Inference API does not offer Nemotron | Verda model list |

## 1. The model

vLLM in Docker, image `vllm/vllm-openai:v0.32.0`, serving an OpenAI-compatible API on port 8000.

The model card's command for one H200 (the 2x H100 command with one GPU):

```bash
vllm serve nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4 \
  --served-model-name nemotron-3.5-super-vl \
  --tensor-parallel-size 1 \
  --max-num-seqs 128 \
  --trust-remote-code \
  --gpu-memory-utilization 0.89 \
  --max-num-batched-tokens 16384 \
  --block-size 64 \
  --prefix-match-unit 64 \
  --compilation_config.max_cudagraph_capture_size 256 \
  --mamba-backend flashinfer \
  --mamba-ssm-cache-dtype float16 \
  --enable-mamba-cache-stochastic-rounding \
  --mamba-cache-philox-rounds 5 \
  --enable-mamba-shared-prefix-checkpoint \
  --mamba-cache-mode align \
  --speculative-config.method mtp \
  --speculative-config.num_speculative_tokens 3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser nemotron_v3 \
  --api-key "$VLLM_API_KEY"
```

(The video flags from the model card are left out: the app sends text and one image.)

Two ways to run it on Verda:

- **A GPU instance** (a virtual machine with Docker). Full control and the weights stay on disk between restarts, so it is the quickest way to find a working configuration. The app can run on the same machine.
- **A serverless container.** The right product once the configuration is known: replicas follow demand and scale to zero. Endpoint `https://containers.verda.com/<deployment-name>/v1`, called with a Verda inference API key.

Point the app at the model in `.env`:

```
LLM_BASE_URL=http://<instance-ip>:8000/v1
LLM_MODEL=nemotron-3.5-super-vl
LLM_API_KEY=<the key vLLM was started with>
LLM_REASONING_EFFORT=
LLM_THINKING=off
```

Then `python scripts/check_model.py` (tools and image input) and `python scripts/evaluate.py`.

## 2. The app

The whole dataset is 61 MB of Parquet and loads in under a second, so the app needs very little: it can share the GPU instance or run on a small CPU instance.

```bash
apt-get update && apt-get install -y python3-venv
cd money-mentor
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py --host 127.0.0.1 --port 8000
```

Copy the project folder from a machine that has `web/brand/` and `data/`: the brand files are not in the repository.

For HTTPS, put Caddy in front. With no domain of our own, `sslip.io` gives the instance IP a hostname, for example `203-0-113-10.sslip.io` for the address 203.0.113.10:

```bash
apt-get install -y caddy
caddy reverse-proxy --from <ip-with-dashes>.sslip.io --to localhost:8000
```

## 3. Managing Verda from the command line

`scripts/verda.py` talks to Verda's cloud API with the credentials in `.env` (`VERDA_CLIENT_ID`, `VERDA_CLIENT_SECRET`):

```bash
python scripts/verda.py balance
python scripts/verda.py types 6000
python scripts/verda.py available
python scripts/verda.py instances
```

## 4. What to say in the Verda submission

- Product used and why: [fill in from what was actually run].
- Why Verda: a bank's customer data and the model that reads it stay on infrastructure the bank controls, in Finland, with an open-weight model. No transaction leaves for a third-party API.
- Path to scale: the engine is stateless SQL over Parquet and the model endpoint is OpenAI-compatible, so the app and the model scale separately, and the model can scale to zero.
