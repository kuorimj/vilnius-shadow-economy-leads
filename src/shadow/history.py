"""Track how companies and places change across monthly snapshots.

Slowly changing dimensions, type 2: one row per version, valid from its first month
(inclusive) to the month it stopped applying (exclusive). valid_to is empty for the
current version. Versions are rebuilt from every stored month on each run, so re-running
or back-filling a month always gives the same result.
"""

from itertools import groupby

from psycopg.rows import dict_row

COMPANY_ATTRIBUTES = ("name", "legal_form", "address", "status", "activity_code")
PLACE_ATTRIBUTES = ("name", "address", "google_category", "price_band")

COMPANY_SNAPSHOTS = f"SELECT snapshot_month, company_code, {', '.join(COMPANY_ATTRIBUTES)} FROM staging.companies"
PLACE_SNAPSHOTS = f"SELECT snapshot_month, cid, {', '.join(PLACE_ATTRIBUTES)} FROM staging.google_places"


def versions(snapshots: list[dict], key: str, attributes: tuple[str, ...]) -> list[dict]:
    months = sorted({row["snapshot_month"] for row in snapshots})
    next_month = dict(zip(months, months[1:]))
    ordered = sorted(snapshots, key=lambda row: (row[key], row["snapshot_month"]))

    result = []
    for entity, rows in groupby(ordered, key=lambda row: row[key]):
        current = None
        last_seen = None
        for row in rows:
            month = row["snapshot_month"]
            values = {attribute: row[attribute] for attribute in attributes}
            if current is not None:
                if next_month[last_seen] != month:
                    current["valid_to"] = next_month[last_seen]
                elif values != {attribute: current[attribute] for attribute in attributes}:
                    current["valid_to"] = month
                if current["valid_to"] is not None:
                    result.append(current)
                    current = None
            if current is None:
                current = {key: entity, **values, "valid_from": month, "valid_to": None}
            last_seen = month
        if last_seen != months[-1]:
            current["valid_to"] = next_month[last_seen]
        result.append(current)
    return result


def replace_table(conn, table: str, columns: tuple[str, ...], rows: list[dict]) -> None:
    conn.execute(f"DELETE FROM {table}")
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row([row[column] for column in columns])


def load_history(conn) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        companies = versions(cur.execute(COMPANY_SNAPSHOTS).fetchall(), "company_code", COMPANY_ATTRIBUTES)
        places = versions(cur.execute(PLACE_SNAPSHOTS).fetchall(), "cid", PLACE_ATTRIBUTES)

    with conn.transaction():
        replace_table(
            conn, "mart.company_versions", ("company_code", *COMPANY_ATTRIBUTES, "valid_from", "valid_to"), companies
        )
        replace_table(conn, "mart.place_versions", ("cid", *PLACE_ATTRIBUTES, "valid_from", "valid_to"), places)

    return {
        "company_versions": len(companies),
        "companies": len({row["company_code"] for row in companies}),
        "place_versions": len(places),
        "places": len({row["cid"] for row in places}),
    }
