"""Snapshot months: typed as "2026-11" on the command line and in folder names, stored as dates."""

import re
from datetime import date

MONTH_FORMAT = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def month_start(month: str) -> date:
    if not MONTH_FORMAT.fullmatch(month):
        raise ValueError(f"expected a month like 2026-11, got {month!r}")
    return date(int(month[:4]), int(month[5:]), 1)


def month_arg(value: str) -> str:
    month_start(value)
    return value
