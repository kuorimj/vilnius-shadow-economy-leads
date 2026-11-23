"""Download and read the declared-activity sources: the company register (JAR) and Sodra."""

import csv
import gzip
import io
import re
import zipfile
from pathlib import Path

import requests

JAR_URL = "https://www.registrucentras.lt/aduomenys/?byla=JAR_IREGISTRUOTI.csv"
SODRA_URL = "https://atvira.sodra.lt/imones/downloads/{year}/monthly-{year}.csv.zip"
JAR_FILE = "JAR_IREGISTRUOTI.csv"
SODRA_FILE = "monthly-{year}.csv"
VILNIUS_PREFIX = "Vilnius,"
SODRA_COLUMN = re.compile(r"\((\w+)\)\s*$")


def declared_dir(month: str, data_dir: str = "data") -> Path:
    return Path(data_dir) / "declared" / month


def download_declared(month: str, data_dir: str = "data") -> None:
    out_dir = declared_dir(month, data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    year = month[:4]

    jar_path = out_dir / JAR_FILE
    if not jar_path.exists():
        print(f"Downloading company register to {jar_path}...", flush=True)
        response = requests.get(JAR_URL, timeout=300)
        response.raise_for_status()
        jar_path.write_bytes(response.content)

    sodra_path = out_dir / SODRA_FILE.format(year=year)
    if not sodra_path.exists():
        print(f"Downloading Sodra {year} data to {sodra_path}...", flush=True)
        response = requests.get(SODRA_URL.format(year=year), timeout=300)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            sodra_path.write_bytes(archive.read(SODRA_FILE.format(year=year)))


def read_jar_vilnius(lines) -> dict[str, dict]:
    companies = {}
    for row in csv.DictReader(lines, delimiter="|"):
        if row["adresas"].startswith(VILNIUS_PREFIX):
            companies[row["ja_kodas"]] = {
                "company_code": row["ja_kodas"],
                "name": row["ja_pavadinimas"],
                "legal_form": row["form_pavadinimas"],
                "address": row["adresas"],
                "registered_on": row["ja_reg_data"] or None,
                "status": row["stat_pavadinimas"],
            }
    return companies


def sodra_key(column: str) -> str:
    match = SODRA_COLUMN.search(column)
    if match is None:
        raise ValueError(f"unexpected Sodra column header: {column!r}")
    return match[1]


def read_sodra(lines, company_codes: set[str]) -> list[dict]:
    reader = csv.reader(lines, delimiter=";")
    header = [sodra_key(column) for column in next(reader)]
    rows = []
    for values in reader:
        row = dict(zip(header, values, strict=True))
        if row["jarCode"] in company_codes:
            rows.append(
                {
                    "company_code": row["jarCode"],
                    "month": f"{row['month'][:4]}-{row['month'][4:]}-01",
                    "insured": int(row["numInsured"]) if row["numInsured"] else None,
                    "avg_wage": row["avgWage"] or None,
                    "contributions": row["tax"] or None,
                    "activity_code": row["ecoActCodeStr"] or None,
                    "activity_name": row["ecoActName"] or None,
                }
            )
    return rows


def extract_name(file_name: str) -> str:
    return file_name.replace(".csv", ".vilnius.csv.gz")

def open_declared(folder: Path, file_name: str, encoding: str):
    full = folder / file_name
    if full.exists():
        return open(full, encoding=encoding, newline="")
    return gzip.open(folder / extract_name(file_name), "rt", encoding=encoding, newline="")

def read_declared(month: str, data_dir: str = "data") -> tuple[dict[str, dict], list[dict]]:
    folder = declared_dir(month, data_dir)
    with open_declared(folder, JAR_FILE, "utf-8") as jar_file:
        companies = read_jar_vilnius(jar_file)
    with open_declared(folder, SODRA_FILE.format(year=month[:4]), "utf-8-sig") as sodra_file:
        monthly = read_sodra(sodra_file, set(companies))
    return companies, monthly