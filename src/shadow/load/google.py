"""Load parsed Google listings into raw.google_listings and build staging.google_places."""

from shadow.extract.google_local import html_from_response, parse_listings

VILNIUS_BOUNDS = {"lat_min": 54.56, "lat_max": 54.84, "lng_min": 25.02, "lng_max": 25.49}

INSERT_RAW = """
    INSERT INTO raw.google_listings (
        snapshot_month, category, area, query, fetched_at, position,
        google_id, cid, name, rating, reviews_count, reviews_rounded,
        google_category, address, price_band, years_in_business, lat, lng, source_file
    ) VALUES (
        %(snapshot_month)s, %(category)s, %(area)s, %(query)s, %(fetched_at)s, %(position)s,
        %(google_id)s, %(cid)s, %(name)s, %(rating)s, %(reviews_count)s, %(reviews_rounded)s,
        %(google_category)s, %(address)s, %(price_band)s, %(years_in_business)s,
        %(lat)s, %(lng)s, %(source_file)s
    )
"""

BUILD_STAGING = """
    INSERT INTO staging.google_places
    WITH usable AS (
        SELECT *
        FROM raw.google_listings
        WHERE snapshot_month = %(month)s
          AND cid IS NOT NULL
          AND lat BETWEEN %(lat_min)s AND %(lat_max)s
          AND lng BETWEEN %(lng_min)s AND %(lng_max)s
    ),
    latest AS (
        SELECT DISTINCT ON (cid) *
        FROM usable
        ORDER BY cid, fetched_at DESC
    ),
    seen AS (
        SELECT
            cid,
            count(*) AS appearances,
            array_agg(DISTINCT category ORDER BY category) AS categories,
            array_agg(DISTINCT area ORDER BY area) AS areas,
            min(position) AS best_position
        FROM usable
        GROUP BY cid
    )
    SELECT
        l.snapshot_month, l.cid, l.google_id, l.name, l.rating, l.reviews_count,
        l.reviews_rounded, l.google_category, l.address, l.price_band, l.years_in_business,
        l.lat, l.lng,
        s.appearances, s.categories, s.areas, s.best_position
    FROM latest l
    JOIN seen s USING (cid)
"""


def listing_rows(month: str, records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        meta = record["meta"]
        listings = parse_listings(html_from_response(record["response"]))
        for position, listing in enumerate(listings, start=1):
            rows.append(
                {
                    "snapshot_month": month,
                    "category": meta["category"],
                    "area": meta["area"],
                    "query": meta["query"],
                    "fetched_at": meta["fetched_at"],
                    "position": position,
                    "google_id": listing.google_id,
                    "cid": listing.cid,
                    "name": listing.name,
                    "rating": listing.rating,
                    "reviews_count": listing.reviews_count,
                    "reviews_rounded": listing.reviews_rounded,
                    "google_category": listing.category,
                    "address": listing.address,
                    "price_band": listing.price_band,
                    "years_in_business": listing.years_in_business,
                    "lat": listing.lat,
                    "lng": listing.lng,
                    "source_file": record["source_file"],
                }
            )
    return rows


def load_google(conn, month: str, records: list[dict]) -> dict:
    rows = listing_rows(month, records)

    with conn.transaction():
        conn.execute("DELETE FROM staging.google_places WHERE snapshot_month = %s", (month,))
        conn.execute("DELETE FROM raw.google_listings WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            cur.executemany(INSERT_RAW, rows)
        conn.execute(BUILD_STAGING, {"month": month, **VILNIUS_BOUNDS})

    raw_count = conn.execute(
        "SELECT count(*) FROM raw.google_listings WHERE snapshot_month = %s", (month,)
    ).fetchone()[0]
    staging_count = conn.execute(
        "SELECT count(*) FROM staging.google_places WHERE snapshot_month = %s", (month,)
    ).fetchone()[0]
    excluded = conn.execute(
        """
        SELECT
            count(DISTINCT cid) FILTER (WHERE lat IS NULL OR lng IS NULL) AS missing_location,
            count(DISTINCT cid) FILTER (WHERE lat IS NOT NULL AND lng IS NOT NULL) AS outside_vilnius
        FROM raw.google_listings r
        WHERE snapshot_month = %(month)s AND cid IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM staging.google_places s
              WHERE s.snapshot_month = r.snapshot_month AND s.cid = r.cid
          )
        """,
        {"month": month},
    ).fetchone()
    return {
        "raw_rows": raw_count,
        "places": staging_count,
        "missing_location": excluded[0],
        "outside_vilnius": excluded[1],
    }