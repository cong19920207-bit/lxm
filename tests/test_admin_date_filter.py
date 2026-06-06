# -*- coding: utf-8 -*-
"""管理端日期区间解析（admin_date_filter）"""

from datetime import datetime

from backend.constants import ADMIN_ERR_QUERY_DATE_FORMAT_INVALID
from backend.services.admin_date_filter import parse_admin_date_range


def test_end_date_includes_full_calendar_day():
    start_dt, end_exclusive, err = parse_admin_date_range("2026-06-04", "2026-06-05")
    assert err is None
    assert start_dt == datetime(2026, 6, 4)
    assert end_exclusive == datetime(2026, 6, 6)
    t = datetime(2026, 6, 5, 2, 22, 28)
    assert start_dt <= t < end_exclusive


def test_start_after_end_returns_error():
    _, _, err = parse_admin_date_range("2026-06-05", "2026-06-04")
    assert err is not None
    assert err.code == ADMIN_ERR_QUERY_DATE_FORMAT_INVALID


def test_invalid_date_format():
    _, _, err = parse_admin_date_range("bad", None)
    assert err is not None
    assert err.code == ADMIN_ERR_QUERY_DATE_FORMAT_INVALID
