"""Prepare a month's raw data for committing, so replay mode works on a clean machine.

- Compresses any uncompressed Google pages (*.json -> *.json.gz).
- Writes Vilnius-only extracts of the declared-data files, as unchanged source lines.
"""

import argparse
import csv
import gzip
import shutil

from shadow.extract.declared import JAR_FILE, SODRA_FILE, VILNIUS_PREFIX, declared_dir, extract_name
from shadow.extract.google_collect import raw_dir
from shadow.months import month_arg


def compress_pages(month: str, data_dir: str = "data") -> int:
    count = 0
    for path in sorted(raw_dir(month, data_dir).glob("*.json")):
        with open(path, "rb") as source, gzip.open(path.with_suffix(".json.gz"), "wb") as target:
            shutil.copyfileobj(source, target)
        path.unlink()
        count += 1
    return count


def write_extract(source_path, target_path, encoding: str, keep) -> int:
    kept = 0
    with open(source_path, encoding=encoding, newline="") as source, \
            gzip.open(target_path, "wt", encoding="utf-8", newline="") as target:
        target.write(next(source))
        for line in source:
            if keep(line):
                target.write(line)
                kept += 1
    return kept


def write_declared_extracts(month: str, data_dir: str = "data") -> tuple[int, int]:
    folder = declared_dir(month, data_dir)
    sodra_file = SODRA_FILE.format(year=month[:4])

    def first_field(line: str, delimiter: str, index: int) -> str:
        return next(csv.reader([line], delimiter=delimiter))[index]

    codes = set()

    def keep_jar(line: str) -> bool:
        if first_field(line, "|", 2).startswith(VILNIUS_PREFIX):
            codes.add(first_field(line, "|", 0))
            return True
        return False

    jar_rows = write_extract(folder / JAR_FILE, folder / extract_name(JAR_FILE), "utf-8", keep_jar)
    sodra_rows = write_extract(
        folder / sodra_file, folder / extract_name(sodra_file), "utf-8-sig",
        lambda line: first_field(line, ";", 1) in codes,
    )
    return jar_rows, sodra_rows


def main():
    parser = argparse.ArgumentParser(description="Prepare a month's raw data for committing")
    parser.add_argument("--month", required=True, type=month_arg, help="Snapshot month, format YYYY-MM")
    args = parser.parse_args()

    pages = compress_pages(args.month)
    jar_rows, sodra_rows = write_declared_extracts(args.month)
    print(f"Compressed {pages} Google pages")
    print(f"Wrote Vilnius extracts: {jar_rows} register rows, {sodra_rows} Sodra rows")


if __name__ == "__main__":
    main()