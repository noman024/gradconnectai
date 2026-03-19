"""Timezone helpers for consistent Dhaka (GMT+6) timestamps."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


DHAKA_TZ = ZoneInfo("Asia/Dhaka")


def now_dhaka() -> datetime:
    """Return current timezone-aware datetime in Asia/Dhaka."""
    return datetime.now(DHAKA_TZ)


def to_dhaka(dt: datetime | None) -> datetime | None:
    """Convert an aware datetime to Asia/Dhaka timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=DHAKA_TZ)
    return dt.astimezone(DHAKA_TZ)
