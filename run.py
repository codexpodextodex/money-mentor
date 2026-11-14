"""Start Money Mentor: fetch the data if it is missing, then serve the app.

    python run.py              # http://localhost:8000
    python run.py --port 8080 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Money Mentor.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from app import config

    if not (config.DATA_DIR / "tx.parquet").exists():
        print("Data not found. Downloading S-Pankki's dataset (about 363 MB) and converting it...")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_data.py")], check=True)

    import uvicorn

    print(f"Money Mentor is starting on http://{args.host}:{args.port}")
    if not config.llm_configured():
        print("No model configured (see .env.example): chat will use the built-in keyword router.")
    uvicorn.run("app.server:app", host=args.host, port=args.port, app_dir=str(ROOT))


if __name__ == "__main__":
    main()
