"""A small command-line client for Verda's cloud API, for deploying Money Mentor.

Reads VERDA_CLIENT_ID and VERDA_CLIENT_SECRET from .env (create them in the Verda
console: project page, Keys, Cloud API Credentials). Nothing here prints a secret.

    python scripts/verda.py balance
    python scripts/verda.py types [filter]          instance types with prices
    python scripts/verda.py available [filter]      what can be started right now, by location
    python scripts/verda.py containers              serverless container GPU types with prices
    python scripts/verda.py images [filter]
    python scripts/verda.py keys                    SSH keys on the account
    python scripts/verda.py add-key NAME PUBFILE    register a public SSH key
    python scripts/verda.py instances               instances on the account
    python scripts/verda.py create HOSTNAME TYPE IMAGE LOCATION KEY_ID [OS_DISK_GB]
    python scripts/verda.py action ID shutdown|start|delete
    python scripts/verda.py deployments             serverless container deployments
    python scripts/verda.py deploy-model NAME [GPU] Nemotron with vLLM as a serverless container
    python scripts/verda.py status NAME             deployment status and replicas
    python scripts/verda.py logs NAME [filter]      container logs
    python scripts/verda.py scale NAME MIN MAX      0 1 lets it sleep when idle, 1 1 keeps one replica warm (untested)
    python scripts/verda.py delete-deployment NAME
    python scripts/verda.py get PATH                any GET, for example: get /locations
"""

from __future__ import annotations

import json
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

TIMEOUT = 40

# https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4.md?hardware=rtx_pro_6000
MODEL_IMAGE = "docker.io/vllm/vllm-openai:v0.32.0"
MODEL_ARGS = [
    "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4",
    "--served-model-name", "nemotron-3.5-super-vl",
    "--trust-remote-code",
    "--max-model-len", "16384",
    "--max-num-seqs", "128",
    "--tensor-parallel-size", "1",
    "--speculative-config.method", "mtp",
    "--speculative-config.num_speculative_tokens", "5",
    "--enable-auto-tool-choice",
    "--tool-call-parser", "qwen3_coder",
    "--reasoning-parser", "nemotron_v3",
]  # fmt: skip


class Verda:
    def __init__(self) -> None:
        if not (config.VERDA_CLIENT_ID and config.VERDA_CLIENT_SECRET):
            raise SystemExit("Set VERDA_CLIENT_ID and VERDA_CLIENT_SECRET in .env first.")
        reply = httpx.post(
            f"{config.VERDA_API}/oauth2/token",
            json={
                "grant_type": "client_credentials",
                "client_id": config.VERDA_CLIENT_ID,
                "client_secret": config.VERDA_CLIENT_SECRET,
            },
            timeout=TIMEOUT,
        )
        if reply.status_code != 200:
            raise SystemExit(f"Verda did not accept the credentials (HTTP {reply.status_code}).")
        self.headers = {"Authorization": f"Bearer {reply.json()['access_token']}"}

    def call(self, method: str, path: str, **kwargs):
        reply = httpx.request(method, f"{config.VERDA_API}{path}", headers=self.headers, timeout=TIMEOUT, **kwargs)
        if reply.status_code >= 400:
            raise SystemExit(f"{method} {path} failed: HTTP {reply.status_code} {reply.text[:600]}")
        if not reply.content:
            return None
        try:
            return reply.json()
        except ValueError:
            return reply.text

    def get(self, path: str, **params):
        return self.call("GET", path, params=params or None)


def show(data) -> None:
    print(json.dumps(data, indent=1, ensure_ascii=False, default=str))


def matches(text: str, wanted: str | None) -> bool:
    return not wanted or wanted.lower() in text.lower()


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit(__doc__)
    command, args = argv[0], argv[1:]
    verda = Verda()

    if command == "balance":
        show(verda.get("/balance"))
    elif command == "types":
        wanted = args[0] if args else None
        for t in sorted(verda.get("/instance-types"), key=lambda t: float(t.get("price_per_hour") or 0)):
            name = t.get("instance_type", "")
            if not matches(name + " " + str(t.get("description", "")), wanted):
                continue
            gpu = t.get("gpu") or {}
            mem = t.get("gpu_memory") or {}
            print(
                f"{name:22} {float(t.get('price_per_hour') or 0):8.3f}/h  spot {float(t.get('spot_price') or 0):7.3f}/h  "
                f"{(t.get('cpu') or {}).get('number_of_cores', '?'):>3} vCPU  {(t.get('memory') or {}).get('size_in_gigabytes', '?'):>4} GB RAM  "
                f"{gpu.get('number_of_gpus', 0)}x {gpu.get('description', '')} {mem.get('size_in_gigabytes', '')} GB  {t.get('currency', '')}"
            )
    elif command == "available":
        wanted = args[0] if args else None
        for place in verda.get("/instance-availability"):
            names = [n for n in place.get("availabilities", []) if matches(n, wanted)]
            print(f"{place.get('location_code')}: {', '.join(names) or '(none match)'}")
    elif command == "containers":
        show(verda.get("/container-types"))
        show(verda.get("/serverless-compute-resources"))
    elif command == "images":
        wanted = args[0] if args else None
        for image in verda.get("/images"):
            line = f"{image.get('image_type', ''):42} {image.get('name', '')}"
            if matches(line, wanted):
                print(line)
    elif command == "keys":
        for key in verda.get("/ssh-keys"):
            print(key.get("id"), key.get("name"), (key.get("fingerprint") or "")[:50])
    elif command == "add-key":
        name, pubfile = args
        public = pathlib.Path(pubfile).read_text(encoding="utf-8").strip()
        if "PRIVATE KEY" in public or not public.startswith(("ssh-", "ecdsa-")):
            raise SystemExit("That does not look like a public key file.")
        show(verda.call("POST", "/ssh-keys", json={"name": name, "key": public}))
    elif command == "instances":
        for i in verda.get("/instances"):
            print(
                f"{i.get('id')}  {i.get('hostname', ''):24} {i.get('instance_type', ''):20} {i.get('status', ''):14} "
                f"{i.get('ip') or '-':16} {i.get('location', '')}  {i.get('price_per_hour', '')}/h"
            )
    elif command == "create":
        hostname, instance_type, image, location, key_id = args[:5]
        body = {
            "hostname": hostname,
            "instance_type": instance_type,
            "image": image,
            "location_code": location,
            "ssh_key_ids": [key_id],
            "contract": "PAY_AS_YOU_GO",
            "is_spot": False,
        }
        if len(args) > 5:
            body["os_volume"] = {"name": f"{hostname}-os", "size": int(args[5])}
        show(verda.call("POST", "/instances", json=body))
    elif command == "action":
        instance_id, action = args
        if action not in ("shutdown", "start", "delete", "boot", "force_shutdown"):
            raise SystemExit("action must be shutdown, start, boot, force_shutdown or delete.")
        show(verda.call("PUT", "/instances", json={"id": instance_id, "action": action}))
    elif command == "deployments":
        for d in verda.get("/container-deployments"):
            scaling = d.get("scaling") or {}
            print(
                f"{d.get('name', ''):28} {(d.get('compute') or {}).get('name', ''):14} "
                f"replicas {scaling.get('min_replica_count')}..{scaling.get('max_replica_count')}  {d.get('endpoint_base_url', '')}"
            )
    elif command == "deploy-model":
        # The vLLM project's recipe for one RTX PRO 6000, as a serverless container.
        name = args[0]
        compute = args[1] if len(args) > 1 else "RTX PRO 6000"
        body = {
            "name": name,
            "is_spot": False,
            "compute": {"name": compute, "size": 1},
            "container_registry_settings": {"is_private": False},
            "scaling": {
                "min_replica_count": 1,
                "max_replica_count": 1,
                "scale_down_policy": {"delay_seconds": 300},
                "scale_up_policy": {"delay_seconds": 0},
                "queue_message_ttl_seconds": 300,
                "concurrent_requests_per_replica": 16,
                "scaling_triggers": {
                    "queue_load": {"threshold": 1},
                    "cpu_utilization": {"enabled": False, "threshold": 80},
                    "gpu_utilization": {"enabled": False, "threshold": 80},
                },
            },
            "containers": [
                {
                    "image": MODEL_IMAGE,
                    "exposed_port": 8000,
                    "healthcheck": {"enabled": True, "port": 8000, "path": "/health"},
                    "entrypoint_overrides": {"enabled": True, "cmd": MODEL_ARGS},
                    "env": [],
                    "volume_mounts": [
                        {"type": "scratch", "mount_path": "/root/.cache/huggingface"},
                        {"type": "memory", "mount_path": "/dev/shm", "size_in_mb": 16384},
                    ],
                }
            ],
        }
        created = verda.call("POST", "/container-deployments", json=body)
        print("created:", created.get("name"), created.get("endpoint_base_url"))
    elif command == "status":
        show(verda.get(f"/container-deployments/{args[0]}/status"))
        show(verda.get(f"/container-deployments/{args[0]}/replicas"))
    elif command == "logs":
        lines = verda.get(f"/container-deployments/{args[0]}/logs")
        wanted = args[1] if len(args) > 1 else None
        for entry in lines if isinstance(lines, list) else [lines]:
            text = entry.get("message", entry) if isinstance(entry, dict) else entry
            if matches(str(text), wanted):
                print(str(text)[:300])
    elif command == "scale":
        name, low, high = args[0], int(args[1]), int(args[2])
        show(verda.call("PATCH", f"/container-deployments/{name}/scaling", json={"min_replica_count": low, "max_replica_count": high}))
    elif command == "delete-deployment":
        verda.call("DELETE", f"/container-deployments/{args[0]}")
        print("deleted", args[0])
    elif command == "get":
        show(verda.get(args[0]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
