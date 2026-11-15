"""Which model hosts the app asks, and in which order."""

import importlib

import httpx
import pytest

from app import agent, config

KEYS = (
    "MM_MODEL_HOST", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "NVIDIA_API_KEY",
    "VERDA_LLM_BASE_URL", "VERDA_INFERENCE_KEY", "VERDA_CC_LLM_BASE_URL", "VERDA_CC_LLM_KEY",
)  # fmt: skip
NVIDIA = {"LLM_BASE_URL": "https://integrate.api.nvidia.com/v1", "LLM_API_KEY": "n", "LLM_MODEL": "nvidia/nemotron"}
SERVERLESS = {"VERDA_LLM_BASE_URL": "https://containers.datacrunch.io/x/v1", "VERDA_INFERENCE_KEY": "s"}
CONFIDENTIAL = {"VERDA_CC_LLM_BASE_URL": "https://203-0-113-10.sslip.io/v1", "VERDA_CC_LLM_KEY": "c"}


@pytest.fixture
def configured(monkeypatch):
    """Load the settings as if .env held exactly these values, and put the real ones back afterwards."""

    def load(**env):
        for key in KEYS:
            monkeypatch.setenv(key, env.get(key, ""))
        return importlib.reload(config)

    yield load
    monkeypatch.undo()
    importlib.reload(config)


def names(cfg):
    return [h["name"] for h in cfg.MODEL_HOSTS]


def test_the_confidential_machine_answers_first_then_serverless_then_nvidia(configured):
    cfg = configured(MM_MODEL_HOST="verda", **NVIDIA, **SERVERLESS, **CONFIDENTIAL)
    assert names(cfg) == ["Verda confidential GPU, Finland", "Verda, Finland", "NVIDIA API"]
    first = cfg.MODEL_HOSTS[0]
    assert first["base_url"] == CONFIDENTIAL["VERDA_CC_LLM_BASE_URL"] and first["thinking"] == "off" and not first["reasoning_effort"]
    # scripts that read the single-host names talk to whoever answers first
    assert cfg.LLM_BASE_URL == first["base_url"] and cfg.LLM_MODEL == first["model"]


def test_each_verda_host_is_optional(configured):
    assert names(configured(MM_MODEL_HOST="verda", **NVIDIA, **SERVERLESS)) == ["Verda, Finland", "NVIDIA API"]
    assert names(configured(MM_MODEL_HOST="verda", **NVIDIA, **CONFIDENTIAL)) == ["Verda confidential GPU, Finland", "NVIDIA API"]
    # without MM_MODEL_HOST=verda only the LLM_* host is asked, whatever else is set
    assert names(configured(MM_MODEL_HOST="nvidia", **NVIDIA, **SERVERLESS, **CONFIDENTIAL)) == ["NVIDIA API"]
    # a host with no key is left out
    assert names(configured(MM_MODEL_HOST="verda", **NVIDIA, VERDA_CC_LLM_BASE_URL="https://x/v1")) == ["NVIDIA API"]


def test_a_host_that_fails_is_skipped_and_the_next_one_answers(configured, monkeypatch):
    configured(MM_MODEL_HOST="verda", **NVIDIA, **SERVERLESS, **CONFIDENTIAL)
    asked = []

    def post(url, json, headers, timeout):
        asked.append((url, timeout.connect))
        if "sslip.io" in url:
            raise httpx.ConnectTimeout("gone")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(agent.httpx, "post", post)
    monkeypatch.setattr(agent, "_skip_until", {})
    agent._post_chat([{"role": "user", "content": "hi"}], use_tools=False)
    assert [u.split("/")[2] for u, _ in asked] == ["203-0-113-10.sslip.io", "containers.datacrunch.io"]
    assert asked[0][1] == config.FIRST_HOST_CONNECT_S  # a host that is gone costs seconds
    assert agent._last_host["name"] == "Verda, Finland"
    # the failed host is left alone for a while: the next question goes straight to the second host
    asked.clear()
    agent._post_chat([{"role": "user", "content": "hi"}], use_tools=False)
    assert [u.split("/")[2] for u, _ in asked] == ["containers.datacrunch.io"]
