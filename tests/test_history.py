import random

from shadow.history import versions

ATTRIBUTES = ("name", "status")


def snapshot(month, code, name="UAB Fabai", status="active"):
    return {"snapshot_month": month, "company_code": code, "name": name, "status": status}


def test_unchanged_company_has_one_open_version():
    rows = [snapshot(month, "1") for month in ("2026-11", "2026-12", "2027-01")]
    assert versions(rows, "company_code", ATTRIBUTES) == [
        {"company_code": "1", "name": "UAB Fabai", "status": "active", "valid_from": "2026-11", "valid_to": None},
    ]


def test_change_closes_the_old_version_and_opens_a_new_one():
    rows = [
        snapshot("2026-11", "1"),
        snapshot("2026-12", "1", name="UAB Fabai Vilnius"),
        snapshot("2027-01", "1", name="UAB Fabai Vilnius", status="in liquidation"),
    ]
    assert [(v["name"], v["status"], v["valid_from"], v["valid_to"]) for v in versions(rows, "company_code", ATTRIBUTES)] == [
        ("UAB Fabai", "active", "2026-11", "2026-12"),
        ("UAB Fabai Vilnius", "active", "2026-12", "2027-01"),
        ("UAB Fabai Vilnius", "in liquidation", "2027-01", None),
    ]


def test_company_missing_from_the_latest_month_is_closed():
    rows = [snapshot("2026-11", "1"), snapshot("2026-12", "1"), snapshot("2026-12", "2")]
    rows.append(snapshot("2027-01", "2"))
    first = [v for v in versions(rows, "company_code", ATTRIBUTES) if v["company_code"] == "1"]
    assert [(v["valid_from"], v["valid_to"]) for v in first] == [("2026-11", "2027-01")]


def test_company_that_disappears_and_returns_gets_a_new_version():
    rows = [snapshot("2026-11", "1"), snapshot("2026-12", "2"), snapshot("2027-01", "1")]
    first = [v for v in versions(rows, "company_code", ATTRIBUTES) if v["company_code"] == "1"]
    assert [(v["valid_from"], v["valid_to"]) for v in first] == [("2026-11", "2026-12"), ("2027-01", None)]


def test_result_does_not_depend_on_load_order():
    rows = [
        snapshot("2026-11", "1"),
        snapshot("2026-12", "1", name="UAB Fabai Vilnius"),
        snapshot("2026-12", "2"),
        snapshot("2027-01", "2", status="in liquidation"),
    ]
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    assert versions(shuffled, "company_code", ATTRIBUTES) == versions(rows, "company_code", ATTRIBUTES)
