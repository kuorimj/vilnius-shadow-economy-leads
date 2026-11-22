"""Load Vilnius companies and their monthly Sodra figures into staging."""

COMPANY_COLUMNS = (
    "snapshot_month", "company_code", "name", "legal_form", "address",
    "registered_on", "status", "activity_code", "activity_name",
)
MONTHLY_COLUMNS = ("snapshot_month", "company_code", "month", "insured", "avg_wage", "contributions")


def latest_activity(monthly: list[dict]) -> dict[str, tuple[str | None, str | None]]:
    latest = {}
    for row in sorted(monthly, key=lambda r: r["month"]):
        latest[row["company_code"]] = (row["activity_code"], row["activity_name"])
    return latest


def load_declared(conn, month: str, companies: dict[str, dict], monthly: list[dict]) -> dict:
    activity = latest_activity(monthly)

    with conn.transaction():
        conn.execute("DELETE FROM staging.company_monthly WHERE snapshot_month = %s", (month,))
        conn.execute("DELETE FROM staging.companies WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            with cur.copy(f"COPY staging.companies ({', '.join(COMPANY_COLUMNS)}) FROM STDIN") as copy:
                for code, company in companies.items():
                    activity_code, activity_name = activity.get(code, (None, None))
                    copy.write_row(
                        (month, *[company[c] for c in COMPANY_COLUMNS[1:7]], activity_code, activity_name)
                    )
            with cur.copy(f"COPY staging.company_monthly ({', '.join(MONTHLY_COLUMNS)}) FROM STDIN") as copy:
                for row in monthly:
                    copy.write_row((month, *[row[c] for c in MONTHLY_COLUMNS[1:]]))

    latest_month = max((row["month"] for row in monthly), default=None)
    return {
        "companies": len(companies),
        "with_sodra": len(activity),
        "monthly_rows": len(monthly),
        "latest_month": latest_month,
    }