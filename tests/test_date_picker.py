# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from datetime import date

from doccon.date_picker import month_weeks, parse_entry_date


def test_month_weeks_sunday_start() -> None:
    weeks = month_weeks(2026, 9)
    assert weeks[0][0] is None
    assert weeks[0][2] == 1
    assert weeks[-1][3] == 30


def test_parse_entry_date_iso_or_today() -> None:
    assert parse_entry_date("2026-09-15") == date(2026, 9, 15)
    assert parse_entry_date("") == date.today()
    assert parse_entry_date("nope", default=date(2026, 1, 1)) == date(2026, 1, 1)
