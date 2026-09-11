import json
from datetime import datetime, timezone
import pandas as pd

from cache_utils import cache_age_minutes, ensure_cache_file, format_cache_age, is_market_open_et


def test_missing_runtime_cache_is_restored(tmp_path):
    bundled = tmp_path / "cache_seed.json"
    runtime = tmp_path / "cache.json"
    payload = {"last_updated_utc": "2026-08-31T14:40:56Z", "data": [{"symbol": "AAA"}]}
    bundled.write_text(json.dumps(payload), encoding="utf-8")

    assert ensure_cache_file(str(runtime), str(bundled)) is True
    assert json.loads(runtime.read_text(encoding="utf-8")) == payload


def test_existing_runtime_cache_is_not_overwritten(tmp_path):
    bundled = tmp_path / "cache_seed.json"
    runtime = tmp_path / "cache.json"
    bundled.write_text('{"data": [{"symbol": "SEED"}]}', encoding="utf-8")
    runtime.write_text('{"data": [{"symbol": "FRESH"}]}', encoding="utf-8")

    assert ensure_cache_file(str(runtime), str(bundled)) is False
    assert json.loads(runtime.read_text(encoding="utf-8"))["data"][0]["symbol"] == "FRESH"


def test_cache_age_and_market_hours_are_calculated():
    now = datetime(2026, 9, 11, 14, 40, tzinfo=timezone.utc)
    updated = "2026-09-11T14:20:00Z"

    assert cache_age_minutes(updated, now) == 20
    assert format_cache_age(16186) == "11 days, 5 hours, 46 minutes"
    assert format_cache_age(65) == "1 hour, 5 minutes"
    assert is_market_open_et(now) is True
    assert is_market_open_et(datetime(2026, 9, 11, 21, 0, tzinfo=timezone.utc)) is False


def test_projection_prices_with_missing_values_are_numeric_safe():
    projection = pd.DataFrame({
        "Low Price": [None, None],
        "Median Price": [None, None],
        "High Price": [None, None],
    })
    rounded = projection.apply(pd.to_numeric, errors="coerce").round(2)
    assert rounded.isna().all().all()
