"""Time helpers. All displayed times are US Eastern (EST or EDT)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ_DISPLAY = ZoneInfo("America/New_York")

# Before this hour (Eastern) we still show the previous day's games,
# so late West Coast games don't vanish at midnight.
NEW_DAY_HOUR_ET = 5


def now_est_str() -> str:
    """Current Eastern time as a string, for the "Last updated" display."""
    return datetime.now(tz=TZ_DISPLAY).strftime("%Y-%m-%d %I:%M:%S %p %Z")


def to_est_dt(iso_ts: str) -> datetime | None:
    """Parses an ISO timestamp (e.g. "2026-05-25T20:40Z") into Eastern time, or None."""
    if not iso_ts:
        return None
    try:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(TZ_DISPLAY)
    except ValueError:
        return None


def to_est_str(iso_ts: str) -> str:
    """
    Converts an ISO timestamp from the sports APIs into a short Eastern time string.

    Example: "2026-05-25T20:40:00Z" -> "4:40PM"
    """
    dt = to_est_dt(iso_ts)
    return dt.strftime("%I:%M%p").lstrip("0") if dt else (iso_ts or "")


def sports_date(now: datetime | None = None) -> str:
    """The date (YYYY-MM-DD) whose games should be shown right now (rolls over at 5 AM ET)."""
    now = now or datetime.now(tz=TZ_DISPLAY)
    return (now - timedelta(hours=NEW_DAY_HOUR_ET)).date().isoformat()
