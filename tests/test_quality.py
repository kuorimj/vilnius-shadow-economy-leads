from shadow.quality import ERROR, INPUT_CHECKS, OUTPUT_CHECKS, WARN, Check, blocking, describe, passes

RANGE = Check("match_share", "matching", "SELECT 1", min_value=0.05, max_value=0.30)


def test_value_inside_the_range_passes():
    assert passes(RANGE, 0.118)
    assert passes(RANGE, 0.05)
    assert passes(RANGE, 0.30)


def test_value_outside_the_range_or_missing_fails():
    assert not passes(RANGE, 0.01)
    assert not passes(RANGE, 0.9)
    assert not passes(RANGE, None)


def test_only_failed_error_checks_block_the_run():
    results = [
        {"check_name": "a", "severity": ERROR, "passed": True},
        {"check_name": "b", "severity": WARN, "passed": False},
        {"check_name": "c", "severity": ERROR, "passed": False},
    ]
    assert [r["check_name"] for r in blocking(results)] == ["c"]


def test_describe_shows_value_and_expected_range():
    result = {"check_name": "match_share", "layer": "matching", "value": 0.01, "min_value": 0.05, "max_value": 0.3}
    assert describe(result) == "match_share (matching): 0.01, expected >= 0.05 and <= 0.3"


def test_check_names_are_unique_and_severities_known():
    checks = INPUT_CHECKS + OUTPUT_CHECKS
    assert len({c.name for c in checks}) == len(checks)
    assert {c.severity for c in checks} <= {ERROR, WARN}
    assert all(c.min_value is not None or c.max_value is not None for c in checks)
