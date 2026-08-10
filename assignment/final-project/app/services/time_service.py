from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


UTC = timezone.utc
JST = ZoneInfo("Asia/Tokyo")


def parse_mlb_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("MLB datetime must include a timezone")
    return parsed.astimezone(UTC)


def to_jst(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Naive datetime is not allowed")
    return value.astimezone(JST)


def jst_day_utc_range(day: date) -> tuple[datetime, datetime]:
    start_jst = datetime.combine(day, time.min, tzinfo=JST)
    end_jst = start_jst + timedelta(days=1)
    return start_jst.astimezone(UTC), end_jst.astimezone(UTC)


def is_on_jst_date(value: datetime, day: date) -> bool:
    return to_jst(value).date() == day

