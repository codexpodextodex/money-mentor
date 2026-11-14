"""Settings, read from the environment (and from a local .env file if present)."""

from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, existing environment wins."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

DATA_DIR = pathlib.Path(os.environ.get("MM_DATA_DIR", ROOT / "data"))
WEB_DIR = ROOT / "web"

# The model is reached through any OpenAI-compatible chat completions API.
# Defaults point at NVIDIA's hosted API; set LLM_BASE_URL to a Verda endpoint
# to keep inference on European infrastructure.
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("NVIDIA_API_KEY") or ""
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_TIMEOUT_S = float(os.environ.get("LLM_TIMEOUT_S", "60"))
# Nemotron can think before answering. "none" gives answers in about 3 seconds
# with the same tool choices in our tests ("low" took about 10); set it empty
# for servers that do not accept the parameter (plain vLLM, for example).
LLM_REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "none")
# The same switch for a model we host ourselves with vLLM, where it goes through
# the chat template: "off" or "on". Leave empty for NVIDIA's hosted API.
LLM_THINKING = os.environ.get("LLM_THINKING", "").strip().lower()

# Verda's cloud API. Only scripts/verda.py reads these.
VERDA_CLIENT_ID = os.environ.get("VERDA_CLIENT_ID", "")
VERDA_CLIENT_SECRET = os.environ.get("VERDA_CLIENT_SECRET", "")
VERDA_API = os.environ.get("VERDA_API", "https://api.verda.com/v1").rstrip("/")


def _host_name(base_url: str) -> str:
    if "nvidia.com" in base_url:
        return "NVIDIA API"
    if "verda.com" in base_url or "datacrunch.io" in base_url:
        return "Verda, Finland"
    return base_url.split("//")[-1].split("/")[0]


def _host(name, base_url, api_key, model, reasoning_effort, thinking) -> dict:
    return {
        "name": name,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "thinking": thinking,
    }


# Where the model runs. The LLM_* settings above describe one host. With MM_MODEL_HOST=verda the
# model we host ourselves on Verda (a serverless container with vLLM) answers first, and the
# LLM_* host stays as the fallback for when the Verda replica is asleep or starting.
VERDA_LLM_BASE_URL = os.environ.get("VERDA_LLM_BASE_URL", "").rstrip("/")
VERDA_LLM_MODEL = os.environ.get("VERDA_LLM_MODEL", "nemotron-3.5-super-vl")
VERDA_INFERENCE_KEY = os.environ.get("VERDA_INFERENCE_KEY", "").strip()
MODEL_HOST = os.environ.get("MM_MODEL_HOST", "").strip().lower()

MODEL_HOSTS = [_host(_host_name(LLM_BASE_URL), LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_REASONING_EFFORT, LLM_THINKING)]
if MODEL_HOST == "verda" and VERDA_LLM_BASE_URL and VERDA_INFERENCE_KEY:
    MODEL_HOSTS.insert(0, _host("Verda, Finland", VERDA_LLM_BASE_URL, VERDA_INFERENCE_KEY, VERDA_LLM_MODEL, "", "off"))
    # The single-host names describe whoever answers first, so scripts keep working unchanged.
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL = VERDA_LLM_BASE_URL, VERDA_INFERENCE_KEY, VERDA_LLM_MODEL
    LLM_REASONING_EFFORT, LLM_THINKING = "", "off"
MODEL_HOSTS = [h for h in MODEL_HOSTS if h["api_key"] and h["model"]]
# How long the first host gets before the next one is asked, and how long a host that failed is left alone.
FIRST_HOST_TIMEOUT_S = float(os.environ.get("LLM_FIRST_HOST_TIMEOUT_S", "30"))
HOST_RETRY_AFTER_S = float(os.environ.get("LLM_HOST_RETRY_AFTER_S", "120"))

# "Today" for the demo. The dataset ends on 2026-09-30, so by default the app
# behaves as if it were that day. Override with MM_TODAY=YYYY-MM-DD.
TODAY_OVERRIDE = os.environ.get("MM_TODAY", "")


def llm_configured() -> bool:
    return bool(MODEL_HOSTS)
