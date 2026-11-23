import random
from datetime import date

from shadow.history import versions

ATTRIBUTES = ("name", "status")
NOV, DEC, JAN = date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)


def snapshot(month, code, name="UAB Fabai", status="active"):
    return {"snapshot_month": month, "company_code": code, "name": name, "status": status}


def test_unchanged_company_has_one_open_version():
    rows = [snapshot(month, "1") for month in (NOV, DEC, JAN)]
    assert versions(rows, "company_code", ATTRIBUTES) == [
        {"company_code": "1", "name": "UAB Fabai", "status": "active", "valid_from": NOV, "valid_to": None},
    ]


def test_change_closes_the_old_version_and_opens_a_new_one():
    rows = [
        snapshot(NOV, "1"),
        snapshot(DEC, "1", name="UAB Fabai Vilnius"),
        snapshot(JAN, "1", name="UAB Fabai Vilnius", status="in liquidation"),
    ]
    result = versions(rows, "company_code", ATTRIBUTES)
    assert [(v["name"], v["status"], v["valid_from"], v["valid_to"]) for v in result] == [
        ("UAB Fabai", "active", NOV, DEC),
        ("UAB Fabai Vilnius", "active", DEC, JAN),
        ("UAB Fabai Vilnius", "in liquidation", JAN, None),
    ]


def test_company_missing_from_the_latest_month_is_closed():
    rows = [snapshot(NOV, "1"), snapshot(DEC, "1"), snapshot(DEC, "2")]
    rows.append(snapshot(JAN, "2"))
    first = [v for v in versions(rows, "company_code", ATTRIBUTES) if v["company_code"] == "1"]
    assert [(v["valid_from"], v["valid_to"]) for v in first] == [(NOV, JAN)]


def test_company_that_disappears_and_returns_gets_a_new_version():
    rows = [snapshot(NOV, "1"), snapshot(DEC, "2"), snapshot(JAN, "1")]
    first = [v for v in versions(rows, "company_code", ATTRIBUTES) if v["company_code"] == "1"]
    assert [(v["valid_from"], v["valid_to"]) for v in first] == [(NOV, DEC), (JAN, None)]


def test_result_does_not_depend_on_load_order():
    rows = [
        snapshot(NOV, "1"),
        snapshot(DEC, "1", name="UAB Fabai Vilnius"),
        snapshot(DEC, "2"),
        snapshot(JAN, "2", status="in liquidation"),
    ]
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    assert versions(shuffled, "company_code", ATTRIBUTES) == versions(rows, "company_code", ATTRIBUTES)
