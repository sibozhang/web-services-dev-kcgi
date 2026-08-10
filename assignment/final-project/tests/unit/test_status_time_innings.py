from datetime import date, datetime, timezone

import pytest

from app.services.game_status_service import GameStatus, normalize_game_status
from app.services.statistics_service import innings_to_outs, outs_to_innings
from app.services.time_service import is_on_jst_date, jst_day_utc_range, to_jst


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"abstractGameState": "Preview", "detailedState": "Scheduled"}, GameStatus.SCHEDULED),
        ({"abstractGameState": "Live", "detailedState": "In Progress"}, GameStatus.LIVE),
        ({"abstractGameState": "Final", "detailedState": "Final"}, GameStatus.FINAL),
        ({"detailedState": "Delayed"}, GameStatus.DELAYED),
        ({"detailedState": "Postponed"}, GameStatus.POSTPONED),
        ({"detailedState": "Suspended"}, GameStatus.SUSPENDED),
        ({"detailedState": "Cancelled"}, GameStatus.CANCELLED),
        ({}, GameStatus.UNKNOWN),
    ],
)
def test_status_mapping(raw, expected):
    assert normalize_game_status(raw) == expected


def test_utc_to_jst_and_date_filter():
    value = datetime(2026, 7, 19, 16, 15, tzinfo=timezone.utc)
    assert to_jst(value).isoformat() == "2026-07-20T01:15:00+09:00"
    assert is_on_jst_date(value, date(2026, 7, 20))
    assert not is_on_jst_date(value, date(2026, 7, 19))


def test_jst_day_range_is_utc_aware():
    start, end = jst_day_utc_range(date(2026, 7, 20))
    assert start.isoformat() == "2026-07-19T15:00:00+00:00"
    assert end.isoformat() == "2026-07-20T15:00:00+00:00"


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        to_jst(datetime(2026, 1, 1))


@pytest.mark.parametrize(("innings", "outs"), [("0.0", 0), ("5.1", 16), ("7.2", 23), ("9.0", 27)])
def test_innings_round_trip(innings, outs):
    assert innings_to_outs(innings) == outs
    assert outs_to_innings(outs) == innings


def test_invalid_innings_rejected():
    with pytest.raises(ValueError):
        innings_to_outs("5.3")

