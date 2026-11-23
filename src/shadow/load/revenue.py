"""Load annual sales revenue per company into staging."""

COLUMNS = ("snapshot_month", "company_code", "period_start", "period_end", "submitted_on", "revenue")


def load_revenue(conn, month: str, rows: list[dict]) -> dict:
    with conn.transaction():
        conn.execute("DELETE FROM staging.company_revenue WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            with cur.copy(f"COPY staging.company_revenue ({', '.join(COLUMNS)}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row((month, *[row[c] for c in COLUMNS[1:]]))
    return {"statements": len(rows), "companies": len({row["company_code"] for row in rows})}
