"""Convert S-Pankki's Junction 2026 CSV files into compact Parquet files.

The raw transactions CSV is about 363 MB. Parquet with zstd brings it down to
a size that loads in seconds and can be shipped to a small server.

Usage:
    python scripts/build_data.py --src path/to/csv/folder [--out data]

The source folder must hold the four files from
https://github.com/hackjunction/Junction-2026-S-pankki
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import duckdb

FILES = {
    "tx": "tx_junction_transactions.csv",
    "customers": "tx_customers_junction.csv",
    "mtg_final": "mtg_tx_customer_link_and_final_mtg_infio.csv",
    "mtg_events": "mtg_negotiation_history.csv",
}

# SAS-style timestamps such as 03OCT24:09:04:04
TS_FORMAT = "%d%b%y:%H:%M:%S"


def sql_path(path: pathlib.Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def build(src: pathlib.Path, out: pathlib.Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES.values():
        if not (src / name).exists():
            sys.exit(f"Missing {name} in {src}")

    con = duckdb.connect()
    csv = {key: sql_path(src / name) for key, name in FILES.items()}
    dst = {key: sql_path(out / f"{key}.parquet") for key in FILES}

    # Transactions: typed, sorted per customer so one customer's rows sit
    # together and a per-customer query only touches a few row groups.
    con.execute(
        f"""
        COPY (
            SELECT
                customer_id,
                bank_account_id AS account_id,
                CAST(tx_date AS DATE) AS tx_date,
                strptime(tx_timestamp, '{TS_FORMAT}') AS tx_ts,
                category,
                CAST(tx_amount_eur AS DOUBLE) AS amount,
                CAST(balance_after_eur AS DOUBLE) AS balance_after,
                transaction_type AS tx_type,
                NULLIF(NULLIF(trim(merchant_id), ''), '.') AS merchant_id,
                NULLIF(NULLIF(trim(mcc_code), ''), '.') AS mcc
            FROM read_csv('{csv["tx"]}', header = true, all_varchar = true)
            ORDER BY customer_id, tx_ts
        ) TO '{dst["tx"]}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 50000)
        """
    )

    # Customers: postal code stays text so leading zeros survive.
    con.execute(
        f"""
        COPY (
            SELECT
                customer_id,
                customer_postal_code AS postal_code,
                CAST(customer_age AS INTEGER) AS age
            FROM read_csv('{csv["customers"]}', header = true, all_varchar = true)
            ORDER BY customer_id
        ) TO '{dst["customers"]}' (FORMAT parquet, COMPRESSION zstd)
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT
                mortgage_customer_id,
                customer_id,
                final_decision,
                NULLIF(rejection_reason, '') AS rejection_reason,
                CAST(final_property_price_eur AS DOUBLE) AS property_price,
                CAST(final_requested_loan_eur AS DOUBLE) AS requested_loan,
                CAST(final_equity_amount_eur AS DOUBLE) AS equity,
                CAST(final_collateral_value_eur AS DOUBLE) AS collateral_value,
                CAST(required_monthly_income_eur AS DOUBLE) AS required_monthly_income,
                CAST(lfinal_loan_to_value AS DOUBLE) AS loan_to_value
            FROM read_csv('{csv["mtg_final"]}', header = true, all_varchar = true)
            ORDER BY mortgage_customer_id
        ) TO '{dst["mtg_final"]}' (FORMAT parquet, COMPRESSION zstd)
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT
                mortgage_customer_id,
                strptime("timestamp", '{TS_FORMAT}') AS event_ts,
                event_type,
                NULLIF(property_id, '') AS property_id,
                NULLIF(property_type, '') AS property_type,
                TRY_CAST(property_price_estimate AS DOUBLE) AS property_price_estimate,
                TRY_CAST(loan_amount AS DOUBLE) AS loan_amount,
                TRY_CAST(equity_amount AS DOUBLE) AS equity_amount,
                NULLIF(collateral_type, '') AS collateral_type,
                TRY_CAST(collateral_value AS DOUBLE) AS collateral_value,
                NULLIF(collateral_status, '') AS collateral_status,
                NULLIF(decision, '') AS decision,
                NULLIF(rejection_reason, '') AS rejection_reason,
                NULLIF(expense_type, '') AS expense_type,
                TRY_CAST(expense_amount AS DOUBLE) AS expense_amount,
                note
            FROM read_csv('{csv["mtg_events"]}', header = true, all_varchar = true)
            ORDER BY mortgage_customer_id, event_ts
        ) TO '{dst["mtg_events"]}' (FORMAT parquet, COMPRESSION zstd)
        """
    )

    for key in FILES:
        rows = con.execute(f"SELECT count(*) FROM '{dst[key]}'").fetchone()[0]
        size_mb = (out / f"{key}.parquet").stat().st_size / 1e6
        print(f"{key:<11} {rows:>9,} rows  {size_mb:7.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--src", required=True, type=pathlib.Path, help="folder with the four CSV files")
    parser.add_argument("--out", default=pathlib.Path("data"), type=pathlib.Path, help="output folder")
    args = parser.parse_args()
    build(args.src, args.out)


if __name__ == "__main__":
    main()
