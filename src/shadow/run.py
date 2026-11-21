import argparse
import os
import sys

import psycopg


def parse_args():
    parser = argparse.ArgumentParser(description="Shadow economy lead pipeline")
    parser.add_argument("--month", required=True, help="Snapshot month, format YYYY-MM")
    parser.add_argument("--mode", choices=["live", "replay"], default="replay")
    return parser.parse_args()


def main():
    args = parse_args()
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
        schemas = [
            row[0]
            for row in conn.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name IN ('raw', 'staging', 'mart') ORDER BY schema_name"
            )
        ]

    print(f"Month: {args.month}, mode: {args.mode}")
    print(f"Connected to: {version}")
    print(f"Schemas found: {schemas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())