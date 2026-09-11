"""Small filesystem helpers for the dashboard cache."""
import os
import shutil
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def ensure_cache_file(cache_file, bundled_cache_file):
    """Restore a bundled snapshot when runtime storage is unavailable.

    Returns True when the snapshot was copied, otherwise False. The caller can
    still read ``bundled_cache_file`` directly when the runtime filesystem is
    read-only.
    """
    if os.path.exists(cache_file) or not os.path.exists(bundled_cache_file):
        return False
    try:
        shutil.copyfile(bundled_cache_file, cache_file)
    except OSError:
        return False
    return True


def cache_age_minutes(last_updated_utc, now=None):
    """Return cache age in minutes, or None when the timestamp is invalid."""
    if not last_updated_utc:
        return None
    try:
        updated = datetime.fromisoformat(str(last_updated_utc).replace('Z', '+00:00'))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return max(0.0, (current.astimezone(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds() / 60.0)
    except (TypeError, ValueError, OverflowError):
        return None


def is_market_open_et(now=None):
    """Return whether the regular US equity session is open in Eastern time."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if ZoneInfo is not None:
        current = current.astimezone(ZoneInfo('America/New_York'))
    else:
        current = current.astimezone(timezone.utc)
    return current.weekday() < 5 and (current.hour, current.minute) >= (9, 30) and (current.hour, current.minute) < (16, 0)
