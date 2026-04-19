"""UTC time helpers used across backend services."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 with trailing Z."""
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_utc_iso(value: str) -> datetime:
    """Parse an ISO timestamp into a timezone-aware UTC datetime."""
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)