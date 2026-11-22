"""Record which category x neighbourhood pages were collected for a month."""

from collections import Counter

from shadow.config import AREAS, CATEGORIES
from shadow.extract.google_local import html_from_response, parse_listings

INSERT_COVERAGE = """
    INSERT INTO staging.google_coverage (
        snapshot_month, category, area, collected, attempts, listings, fetched_at
    ) VALUES (
        %(snapshot_month)s, %(category)s, %(area)s, %(collected)s, %(attempts)s, %(listings)s, %(fetched_at)s
    )
"""


def coverage_rows(month: str, records: list[dict], attempts: list[dict]) -> list[dict]:
    pages = {(r["meta"]["category"], r["meta"]["area"]): r for r in records}
    attempt_counts = Counter((a["category"], a["area"]) for a in attempts)

    rows = []
    for category in CATEGORIES:
        for area in AREAS:
            page = pages.get((category, area))
            rows.append(
                {
                    "snapshot_month": month,
                    "category": category,
                    "area": area,
                    "collected": page is not None,
                    "attempts": attempt_counts[(category, area)],
                    "listings": len(parse_listings(html_from_response(page["response"]))) if page else 0,
                    "fetched_at": page["meta"]["fetched_at"] if page else None,
                }
            )
    return rows


def load_coverage(conn, month: str, records: list[dict], attempts: list[dict]) -> list[dict]:
    rows = coverage_rows(month, records, attempts)
    with conn.transaction():
        conn.execute("DELETE FROM staging.google_coverage WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            cur.executemany(INSERT_COVERAGE, rows)
    return [row for row in rows if not row["collected"]]