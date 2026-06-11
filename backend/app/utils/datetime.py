from datetime import datetime, timezone


def to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def parse_utc_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return to_utc_naive(value)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return to_utc_naive(datetime.fromisoformat(text))
    return None


def isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    utc_value = value
    if utc_value.tzinfo is not None:
        utc_value = utc_value.astimezone(timezone.utc).replace(tzinfo=None)
    return f"{utc_value.isoformat()}Z"
