"""Download S-Pankki's Junction 2026 dataset and convert it to Parquet.

The dataset lives in https://github.com/hackjunction/Junction-2026-S-pankki.
The transactions file (363 MB) is stored with Git LFS, so it is fetched from
GitHub's LFS media host; the three small files come from the raw host.

Usage:
    python scripts/fetch_data.py            # downloads to data/raw, builds data/*.parquet
    python scripts/fetch_data.py --keep-csv # keep the CSV files afterwards
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_data  # noqa: E402

REPO = "hackjunction/Junction-2026-S-pankki"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
LFS = f"https://media.githubusercontent.com/media/{REPO}/{BRANCH}"

SOURCES = {
    "tx_junction_transactions.csv": LFS,
    "tx_customers_junction.csv": RAW,
    "mtg_tx_customer_link_and_final_mtg_infio.csv": RAW,
    "mtg_negotiation_history.csv": RAW,
}


def download(url: str, dest: pathlib.Path) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(part, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {dest.name}: {done / 1e6:6.0f} / {total / 1e6:.0f} MB", end="", flush=True)
    print()
    part.replace(dest)
    with open(dest, "rb") as check:
        if check.read(40).startswith(b"version https://git-lfs"):
            sys.exit(f"{dest.name} is a Git LFS pointer, not the data. Download it from the GitHub page instead.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=ROOT / "data", type=pathlib.Path)
    parser.add_argument("--keep-csv", action="store_true", help="keep the downloaded CSV files")
    args = parser.parse_args()

    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, base in SOURCES.items():
        dest = raw_dir / name
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"  {name}: already downloaded")
            continue
        download(f"{base}/{name}", dest)
    build_data.build(raw_dir, args.out)
    if not args.keep_csv:
        shutil.rmtree(raw_dir)


if __name__ == "__main__":
    main()
