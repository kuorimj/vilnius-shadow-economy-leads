import json
from pathlib import Path

from shadow.config import AREAS, CATEGORIES
from shadow.load.coverage import coverage_rows

FIXTURE = Path(__file__).parent / "fixtures" / "google_local_kavine_seskine.json"


def test_coverage_marks_collected_and_missing_pages():
    response = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = [
        {
            "meta": {"category": "cafe_restaurant", "area": "seskine", "fetched_at": "2026-11-21T10:00:00+00:00"},
            "response": response,
        }
    ]
    attempts = [
        {"category": "cafe_restaurant", "area": "seskine", "status": 500},
        {"category": "cafe_restaurant", "area": "seskine", "status": 200},
        {"category": "car_repair", "area": "rasos", "status": 500},
    ]

    rows = coverage_rows("2026-11", records, attempts)
    by_key = {(row["category"], row["area"]): row for row in rows}

    assert len(rows) == len(CATEGORIES) * len(AREAS)
    assert by_key[("cafe_restaurant", "seskine")]["collected"] is True
    assert by_key[("cafe_restaurant", "seskine")]["attempts"] == 2
    assert by_key[("cafe_restaurant", "seskine")]["listings"] == 20
    assert by_key[("car_repair", "rasos")]["collected"] is False
    assert by_key[("car_repair", "rasos")]["attempts"] == 1
    assert by_key[("car_repair", "rasos")]["listings"] == 0
    assert by_key[("hair_beauty", "zirmunai")]["attempts"] == 0