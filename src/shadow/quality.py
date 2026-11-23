"""Data quality checks between layers.

Each check is one SQL query returning one number, an allowed range and a severity.
A failed "error" check stops the run before scoring, so no lead list is published from
broken data. A failed "warn" check is reported and stored, but the run continues.
Thresholds come from the November 2026 baseline, with room for normal month-to-month change.
"""

from dataclasses import dataclass
from datetime import date

ERROR = "error"
WARN = "warn"

LATEST_SODRA_MONTH = (
    "(SELECT max(month) FROM staging.company_monthly WHERE snapshot_month = %(month)s)"
)
CONFIRMED_COMPANIES = (
    "(SELECT DISTINCT company_code FROM staging.place_matches "
    "WHERE snapshot_month = %(month)s AND match_status = 'confirmed')"
)


@dataclass(frozen=True)
class Check:
    name: str
    layer: str
    sql: str
    min_value: float | None = None
    max_value: float | None = None
    severity: str = ERROR


INPUT_CHECKS = [
    Check(
        "google_pages_collected", "google",
        "SELECT avg(collected::int) FROM staging.google_coverage WHERE snapshot_month = %(month)s",
        min_value=0.75,
    ),
    Check(
        "google_listings_per_page", "google",
        "SELECT count(*)::float / nullif(count(DISTINCT source_file), 0) "
        "FROM raw.google_listings WHERE snapshot_month = %(month)s",
        min_value=10,
    ),
    Check(
        "google_fetched_in_snapshot_month", "google",
        "SELECT avg((date_trunc('month', fetched_at AT TIME ZONE 'UTC')::date = %(month)s)::int) "
        "FROM raw.google_listings WHERE snapshot_month = %(month)s",
        min_value=1,
    ),
    Check(
        "google_missing_place_id", "google",
        "SELECT avg((cid IS NULL)::int) FROM raw.google_listings WHERE snapshot_month = %(month)s",
        max_value=0.05,
    ),
    Check(
        "google_missing_location", "google",
        "SELECT avg((lat IS NULL OR lng IS NULL)::int) FROM raw.google_listings WHERE snapshot_month = %(month)s",
        max_value=0.05,
    ),
    Check(
        "google_missing_review_count", "google",
        "SELECT avg((reviews_count IS NULL)::int) FROM raw.google_listings WHERE snapshot_month = %(month)s",
        max_value=0.10, severity=WARN,
    ),
    Check(
        "google_places_kept", "google",
        "SELECT (SELECT count(*) FROM staging.google_places WHERE snapshot_month = %(month)s)::float "
        "/ nullif((SELECT count(DISTINCT cid) FROM raw.google_listings WHERE snapshot_month = %(month)s), 0)",
        min_value=0.9,
    ),
    Check(
        "register_companies", "declared",
        "SELECT count(*) FROM staging.companies WHERE snapshot_month = %(month)s",
        min_value=50_000,
    ),
    Check(
        "sodra_months_behind", "declared",
        "SELECT (extract(year FROM %(month)s::date) - extract(year FROM max(month))) * 12 "
        "+ extract(month FROM %(month)s::date) - extract(month FROM max(month)) "
        "FROM staging.company_monthly WHERE snapshot_month = %(month)s",
        max_value=3,
    ),
    Check(
        "sodra_companies_latest_month", "declared",
        "SELECT count(*) FROM staging.company_monthly "
        f"WHERE snapshot_month = %(month)s AND month = {LATEST_SODRA_MONTH}",
        min_value=30_000,
    ),
    Check(
        "sodra_missing_insured", "declared",
        "SELECT avg((insured IS NULL)::int) FROM staging.company_monthly "
        f"WHERE snapshot_month = %(month)s AND month = {LATEST_SODRA_MONTH}",
        max_value=0.05,
    ),
    Check(
        "confirmed_match_share", "matching",
        "SELECT avg((match_status = 'confirmed')::int) FROM staging.place_matches WHERE snapshot_month = %(month)s",
        min_value=0.05, max_value=0.30,
    ),
    Check(
        "revenue_coverage", "revenue",
        "SELECT avg((EXISTS (SELECT 1 FROM staging.company_revenue r "
        "WHERE r.snapshot_month = %(month)s AND r.company_code = c.company_code))::int) "
        f"FROM {CONFIRMED_COMPANIES} c",
        min_value=0.8,
    ),
    Check(
        "revenue_years_behind", "revenue",
        "SELECT extract(year FROM %(month)s::date) - max(extract(year FROM period_end)) "
        "FROM staging.company_revenue WHERE snapshot_month = %(month)s",
        max_value=2, severity=WARN,
    ),
]

OUTPUT_CHECKS = [
    Check(
        "leads_found", "leads",
        "SELECT count(*) FROM mart.leads WHERE snapshot_month = %(month)s",
        min_value=1, severity=WARN,
    ),
    Check(
        "lead_share_of_confirmed", "leads",
        "SELECT (SELECT count(*) FROM mart.leads WHERE snapshot_month = %(month)s)::float "
        f"/ nullif((SELECT count(*) FROM {CONFIRMED_COMPANIES} c), 0)",
        max_value=0.25, severity=WARN,
    ),
]

INSERT_RESULT = """
    INSERT INTO mart.quality_checks (
        snapshot_month, check_name, layer, severity, value, min_value, max_value, passed
    ) VALUES (
        %(snapshot_month)s, %(check_name)s, %(layer)s, %(severity)s, %(value)s,
        %(min_value)s, %(max_value)s, %(passed)s
    )
"""


def passes(check: Check, value: float | None) -> bool:
    if value is None:
        return False
    if check.min_value is not None and value < check.min_value:
        return False
    if check.max_value is not None and value > check.max_value:
        return False
    return True


def run_checks(conn, month: date, checks: list[Check], reset: bool = False) -> list[dict]:
    results = []
    for check in checks:
        value = conn.execute(check.sql, {"month": month}).fetchone()[0]
        value = float(value) if value is not None else None
        results.append(
            {
                "snapshot_month": month,
                "check_name": check.name,
                "layer": check.layer,
                "severity": check.severity,
                "value": value,
                "min_value": check.min_value,
                "max_value": check.max_value,
                "passed": passes(check, value),
            }
        )

    with conn.transaction():
        if reset:
            conn.execute("DELETE FROM mart.quality_checks WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            cur.executemany(INSERT_RESULT, results)
    return results


def blocking(results: list[dict]) -> list[dict]:
    return [r for r in results if r["severity"] == ERROR and not r["passed"]]


def describe(result: dict) -> str:
    bounds = []
    if result["min_value"] is not None:
        bounds.append(f">= {result['min_value']:g}")
    if result["max_value"] is not None:
        bounds.append(f"<= {result['max_value']:g}")
    value = "no value" if result["value"] is None else f"{result['value']:.3g}"
    return f"{result['check_name']} ({result['layer']}): {value}, expected {' and '.join(bounds)}"
