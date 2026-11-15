#!/usr/bin/env bash
# Start Nemotron 3.5 Super VL with vLLM on one Verda RTX PRO 6000 (96 GB, Blackwell).
#
# This is the vLLM project's own recipe for this card:
#   https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4.md?hardware=rtx_pro_6000
# with three additions of ours: the server listens on 127.0.0.1:8001 only, it requires the
# key the app holds, and it reads the weights from /root/hf without going online.
#
# What we learned on 14 Nov 2026:
#   - The model card's commands for H200 and GB200, with their extra tuning flags, start on
#     this card but answer in garbage. Use the recipe for the card you have.
#   - On a confidential-computing machine the GPU refuses work ("Error 802: system not yet
#     initialized") until it is switched to the ready state, after every boot.
#   - On a confidential-computing machine vLLM 0.32.0 must use its older model runner
#     (VLLM_USE_V2_MODEL_RUNNER=0), or every answer is junk. This script sets both.
#
# The weights were downloaded beforehand with
#   HF_HOME=/root/hf hf download nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4
set -euo pipefail

APP_DIR="${APP_DIR:-/root/money-mentor}"
HF_DIR="${HF_DIR:-/root/hf}"
IMAGE="${IMAGE:-vllm/vllm-openai:v0.32.0}"
CONTEXT="${CONTEXT:-16384}"
SEQS="${SEQS:-128}"
DRAFT_TOKENS="${DRAFT_TOKENS:-5}"   # 0 switches the model's built-in draft head (MTP) off

# The key the app already uses, handed to the container through a file that only root can read.
umask 077
grep '^LLM_API_KEY=' "$APP_DIR/.env" | sed 's/^LLM_API_KEY=/VLLM_API_KEY=/' > "$APP_DIR/vllm.env"

RUNNER=()
if nvidia-smi conf-compute -f 2>/dev/null | grep -q 'CC status: ON'; then
  nvidia-smi conf-compute -srs 1 >/dev/null
  nvidia-smi conf-compute -grs
  # vLLM up to 0.33 answers in junk on a confidential GPU with its default (V2) model runner:
  # the GPU reads stale input (vllm-project/vllm#57224). The older runner is correct.
  RUNNER=(-e VLLM_USE_V2_MODEL_RUNNER=0)
fi

EXTRA=()
if [ "$DRAFT_TOKENS" != "0" ]; then
  EXTRA+=(--speculative-config.method mtp --speculative-config.num_speculative_tokens "$DRAFT_TOKENS")
fi
# Anything else to try, as one string: EXTRA_ARGS="--flag value"
# shellcheck disable=SC2206
if [ -n "${EXTRA_ARGS:-}" ]; then EXTRA+=(${EXTRA_ARGS}); fi

docker rm -f nemotron >/dev/null 2>&1 || true
docker run -d --name nemotron --gpus all --ipc=host --restart "${RESTART:-no}" \
  -p 127.0.0.1:8001:8000 \
  -v "$HF_DIR":/root/.cache/huggingface \
  -e HF_HUB_OFFLINE=1 \
  "${RUNNER[@]}" \
  --env-file "$APP_DIR/vllm.env" \
  "$IMAGE" \
  nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4 \
  --served-model-name nemotron-3.5-super-vl \
  --trust-remote-code \
  --max-model-len "$CONTEXT" \
  --max-num-seqs "$SEQS" \
  --tensor-parallel-size 1 \
  "${EXTRA[@]}" \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser nemotron_v3

echo "started; follow with: docker logs -f nemotron"
