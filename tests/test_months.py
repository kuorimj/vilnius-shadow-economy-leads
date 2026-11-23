from datetime import date

import pytest

from shadow.months import month_arg, month_start


def test_month_is_stored_as_its_first_day():
    assert month_start("2026-11") == date(2026, 11, 1)
    assert month_start("2027-01") == date(2027, 1, 1)


@pytest.mark.parametrize("value", ["2026-13", "2026-1", "2026-00", "Nov 2026", "2026-11-01", ""])
def test_malformed_month_is_rejected(value):
    with pytest.raises(ValueError):
        month_start(value)


def test_command_line_keeps_the_typed_form():
    assert month_arg("2026-11") == "2026-11"
