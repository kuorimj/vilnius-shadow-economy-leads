"""Link Google places to registered companies, with an explicit confidence level."""

from dataclasses import dataclass

from shadow.config import CATEGORY_ACTIVITIES
from shadow.match.names import distinctive_name, street_key

MIN_SIMILARITY = 0.8
MIN_NAME_LENGTH = 4

FIND_CANDIDATES = """
    SELECT p.cid, c.company_code, similarity(p.name_key, c.name_key) AS name_similarity
    FROM match_places p
    JOIN match_companies c ON p.name_key %% c.name_key
    WHERE length(p.name_key) >= %(min_length)s
"""

INSERT_MATCH = """
    INSERT INTO staging.place_matches (
        snapshot_month, cid, match_status, company_code, name_similarity,
        activity_fits, same_address, candidates
    ) VALUES (
        %(snapshot_month)s, %(cid)s, %(match_status)s, %(company_code)s, %(name_similarity)s,
        %(activity_fits)s, %(same_address)s, %(candidates)s
    )
"""


@dataclass
class Candidate:
    company_code: str
    name_similarity: float
    activity_fits: bool
    same_address: bool

    @property
    def confirmed(self) -> bool:
        return self.activity_fits or self.same_address


def activity_fits(categories: list[str], activity_code: str | None) -> bool:
    if not activity_code:
        return False
    return any(activity_code.startswith(CATEGORY_ACTIVITIES[c]) for c in categories)


def decide(candidates: list[Candidate]) -> tuple[str, Candidate | None]:
    if not candidates:
        return "unmatched", None
    confirmed = [c for c in candidates if c.confirmed]
    if len(confirmed) == 1:
        return "confirmed", confirmed[0]
    if len(candidates) == 1:
        return "possible", candidates[0]
    return "ambiguous", None


def load_matches(conn, month: str) -> dict[str, int]:
    places = conn.execute(
        "SELECT cid, name, address, categories FROM staging.google_places WHERE snapshot_month = %s",
        (month,),
    ).fetchall()
    companies = conn.execute(
        "SELECT company_code, name, address, activity_code FROM staging.companies WHERE snapshot_month = %s",
        (month,),
    ).fetchall()
    place_info = {cid: (street_key(address), categories) for cid, _, address, categories in places}
    company_info = {code: (street_key(address), activity) for code, _, address, activity in companies}

    with conn.transaction():
        conn.execute("CREATE TEMP TABLE match_places (cid text, name_key text) ON COMMIT DROP")
        conn.execute("CREATE TEMP TABLE match_companies (company_code text, name_key text) ON COMMIT DROP")
        with conn.cursor() as cur:
            with cur.copy("COPY match_places (cid, name_key) FROM STDIN") as copy:
                for cid, name, _, _ in places:
                    copy.write_row((cid, distinctive_name(name)))
            with cur.copy("COPY match_companies (company_code, name_key) FROM STDIN") as copy:
                for code, name, _, _ in companies:
                    copy.write_row((code, distinctive_name(name)))
        conn.execute("CREATE INDEX ON match_companies USING gin (name_key gin_trgm_ops)")
        conn.execute(f"SET LOCAL pg_trgm.similarity_threshold = {MIN_SIMILARITY}")
        rows = conn.execute(FIND_CANDIDATES, {"min_length": MIN_NAME_LENGTH}).fetchall()

        candidates: dict[str, list[Candidate]] = {cid: [] for cid in place_info}
        for cid, code, similarity in rows:
            place_street, categories = place_info[cid]
            company_street, activity = company_info[code]
            candidates[cid].append(
                Candidate(
                    company_code=code,
                    name_similarity=round(similarity, 2),
                    activity_fits=activity_fits(categories, activity),
                    same_address=place_street is not None and place_street == company_street,
                )
            )

        conn.execute("DELETE FROM staging.place_matches WHERE snapshot_month = %s", (month,))
        counts = {"confirmed": 0, "possible": 0, "ambiguous": 0, "unmatched": 0}
        with conn.cursor() as cur:
            for cid, found in candidates.items():
                status, chosen = decide(found)
                counts[status] += 1
                cur.execute(
                    INSERT_MATCH,
                    {
                        "snapshot_month": month,
                        "cid": cid,
                        "match_status": status,
                        "company_code": chosen.company_code if chosen else None,
                        "name_similarity": chosen.name_similarity if chosen else None,
                        "activity_fits": chosen.activity_fits if chosen else None,
                        "same_address": chosen.same_address if chosen else None,
                        "candidates": len(found),
                    },
                )
    return counts


def confirmed_company_codes(conn, month: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT company_code FROM staging.place_matches "
        "WHERE snapshot_month = %s AND match_status = 'confirmed' ORDER BY company_code",
        (month,),
    )
    return [code for (code,) in rows]
