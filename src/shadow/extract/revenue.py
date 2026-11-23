"""Fetch and read annual sales revenue from Registrų centras' financial statements.

The data comes from the national open data API (get.data.gov.lt). Only companies already
confirmed by matching are fetched, and every API answer is saved unchanged, so replay mode
needs no network.
"""

import argparse
import gzip
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from shadow.extract.declared import declared_dir

API_BASE = "https://get.data.gov.lt/datasets/gov/rc/jar"
COMPANY_URL = API_BASE + "/iregistruoti/JuridinisAsmuo?ja_kodas={code}"
REVENUE_URL = (
    API_BASE + '/pelno_ataskaitos/PelnoAtaskaita?juridinis_asmuo._id="{entity_id}"'
    '&line_type_id="{line}"&limit({limit})'
)
REVENUE_LINE = "ISLT00345"  # PARDAVIMO PAJAMOS (sales revenue): same ID in every statement template
PAGE_LIMIT = 500
TIMEOUT = 60
REVENUE_FILE = "revenue.jsonl.gz"


def revenue_path(month: str, data_dir: str = "data") -> Path:
    return declared_dir(month, data_dir) / REVENUE_FILE


def api_session() -> requests.Session:
    retry = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_company(session: requests.Session, code: str) -> dict:
    response = session.get(COMPANY_URL.format(code=code), timeout=TIMEOUT)
    response.raise_for_status()
    entities = response.json()["_data"]
    entity = entities[0] if entities else None

    statements = []
    if entity:
        url = REVENUE_URL.format(entity_id=entity["_id"], line=REVENUE_LINE, limit=PAGE_LIMIT)
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        statements = response.json()["_data"]
        if len(statements) >= PAGE_LIMIT:
            raise RuntimeError(f"{code}: {len(statements)} revenue rows, more than one page")

    return {
        "company_code": code,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entity": entity,
        "statements": statements,
    }


def read_revenue_raw(month: str, data_dir: str = "data") -> list[dict]:
    path = revenue_path(month, data_dir)
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def collect_revenue(month: str, company_codes: list[str], data_dir: str = "data") -> dict:
    path = revenue_path(month, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    already = {record["company_code"] for record in read_revenue_raw(month, data_dir)}
    todo = sorted(set(company_codes) - already)

    session = api_session()
    for code in todo:
        record = fetch_company(session, code)
        with gzip.open(path, "at", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"fetched": len(todo), "already_had": len(set(company_codes) & already)}


def revenue_rows(records: list[dict]) -> list[dict]:
    rows = {}
    for record in records:
        for statement in record["statements"]:
            key = (
                record["company_code"],
                statement["laikotarpis_nuo"],
                statement["laikotarpis_iki"],
                statement["reg_date"],
            )
            rows[key] = {
                "company_code": record["company_code"],
                "period_start": statement["laikotarpis_nuo"],
                "period_end": statement["laikotarpis_iki"],
                "submitted_on": statement["reg_date"],
                "revenue": statement["reiksme"],
            }
    return sorted(rows.values(), key=lambda r: (r["company_code"], r["period_end"], r["submitted_on"]))


def main():
    from shadow.match.places import confirmed_company_codes
    from shadow.months import month_arg, month_start

    parser = argparse.ArgumentParser(description="Fetch revenue for companies confirmed by matching")
    parser.add_argument("--month", required=True, type=month_arg, help="Snapshot month, format YYYY-MM")
    args = parser.parse_args()

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        codes = confirmed_company_codes(conn, month_start(args.month))
    summary = collect_revenue(args.month, codes)
    print(f"Revenue: fetched {summary['fetched']} companies, already had {summary['already_had']}")


if __name__ == "__main__":
    main()
