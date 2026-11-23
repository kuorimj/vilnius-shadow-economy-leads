import gzip
import json

from shadow.extract import revenue
from shadow.extract.revenue import collect_revenue, read_revenue_raw, revenue_rows


def statement(start, end, submitted, value):
    return {
        "_type": "datasets/gov/rc/jar/pelno_ataskaitos/PelnoAtaskaita",
        "line_type_id": "ISLT00345",
        "line_name": "PARDAVIMO PAJAMOS",
        "reiksme": value,
        "laikotarpis_nuo": start,
        "laikotarpis_iki": end,
        "reg_date": submitted,
    }


FABAI = {
    "company_code": "303001740",
    "fetched_at": "2026-11-23T09:30:00+00:00",
    "entity": {"_id": "e18d9315-1fef-4e69-8935-fc48f9a1c439", "ja_kodas": 303001740},
    "statements": [
        statement("2024-01-01", "2024-12-31", "2025-05-29", 426740),
        statement("2024-01-01", "2024-12-31", "2025-05-29", 426740),
        statement("2023-01-01", "2023-12-31", "2024-05-16", 358257),
    ],
}


def test_revenue_rows_drop_duplicate_statements():
    rows = revenue_rows([FABAI])
    assert rows == [
        {"company_code": "303001740", "period_start": "2023-01-01", "period_end": "2023-12-31",
         "submitted_on": "2024-05-16", "revenue": 358257},
        {"company_code": "303001740", "period_start": "2024-01-01", "period_end": "2024-12-31",
         "submitted_on": "2025-05-29", "revenue": 426740},
    ]


def test_company_not_in_the_register_has_no_rows():
    missing = {"company_code": "1", "fetched_at": "", "entity": None, "statements": []}
    assert revenue_rows([missing]) == []


def test_collect_fetches_only_companies_not_saved_yet(tmp_path, monkeypatch):
    path = tmp_path / "declared" / "2026-11" / "revenue.jsonl.gz"
    path.parent.mkdir(parents=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(json.dumps(FABAI) + "\n")

    fetched = []

    def fake_fetch(session, code):
        fetched.append(code)
        return {"company_code": code, "fetched_at": "", "entity": None, "statements": []}

    monkeypatch.setattr(revenue, "fetch_company", fake_fetch)
    summary = collect_revenue("2026-11", ["303001740", "307060992"], data_dir=str(tmp_path))

    assert fetched == ["307060992"]
    assert summary == {"fetched": 1, "already_had": 1}
    assert [r["company_code"] for r in read_revenue_raw("2026-11", data_dir=str(tmp_path))] == [
        "303001740", "307060992",
    ]
