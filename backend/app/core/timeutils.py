from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "America/Sao_Paulo"


def get_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_now(tz_name: str | None) -> datetime:
    return utcnow().astimezone(get_zone(tz_name))


def local_day_bounds(tz_name: str | None, now: datetime | None = None, day: date | None = None) -> tuple[datetime, datetime]:
    """Inicio e fim (exclusivo) do dia no fuso do estabelecimento, como datetimes com fuso."""
    zone = get_zone(tz_name)
    target = day or (now or utcnow()).astimezone(zone).date()
    start = datetime.combine(target, time.min, tzinfo=zone)
    return start, datetime.combine(target + timedelta(days=1), time.min, tzinfo=zone)


def to_local(value: datetime, tz_name: str | None) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_zone(tz_name))
