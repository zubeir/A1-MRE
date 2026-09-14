import json

from top10_rotation import (
    SIGNAL_DROP,
    SIGNAL_HOLD,
    SIGNAL_INVEST,
    calculate_persistence,
    classify_mtd,
    record_rotation_confirmation,
    score_rotation_candidates,
    select_rotation_tickers,
)


def test_persistence_counts_unique_monthly_appearances():
    cohorts = [[{"symbol": "AAA"}, {"symbol": "AAA"}, {"symbol": "BBB"}], [{"symbol": "AAA"}], [{"symbol": "CCC"}]]
    result = calculate_persistence(cohorts)
    assert result["AAA"] == {"appearance_count_6m": 2, "appearance_score": 67}
    assert result["BBB"]["appearance_score"] == 33


def test_mtd_classification():
    assert classify_mtd(0.01) == ("Green", 100)
    assert classify_mtd(0) == ("Yellow", 50)
    assert classify_mtd(-0.01) == ("Red", 0)


def test_composite_score_and_signal():
    rows = score_rotation_candidates(
        [{"symbol": "AAA", "sector": "Technology", "mtd": 0.1}],
        [[{"symbol": "AAA", "sector": "Technology"}]] * 5,
        ["Technology"],
        [{"symbol": "AAA"}],
        None,  # No current dataset provided
    )
    row = rows[0]
    assert row["appearance_count_6m"] == 6
    assert row["rotation_score"] == 100.0
    assert row["rotation_signal"] == SIGNAL_INVEST


def test_signal_thresholds_and_fallback_selection():
    candidates = [
        {"symbol": "INV", "rotation_score": 70, "rotation_signal": SIGNAL_INVEST},
        {"symbol": "HOLD", "rotation_score": 40, "rotation_signal": SIGNAL_HOLD},
        {"symbol": "DROP", "rotation_score": 39, "rotation_signal": SIGNAL_DROP},
    ]
    selected = select_rotation_tickers(candidates, limit=2)
    assert [row["symbol"] for row in selected] == ["INV", "HOLD"]


def test_confirmation_appends_json(tmp_path):
    path = tmp_path / "rotation_history.json"
    record_rotation_confirmation([{"symbol": "AAA", "rotation_score": 80}], "Equal-weight", str(path))
    payload = json.loads(path.read_text())
    assert payload[0]["tickers"] == ["AAA"]
    assert payload[0]["allocation_mode"] == "Equal-weight"


def test_historical_candidates_included_in_pool():
    """Test that historical top performers are included in rotation candidate pool."""
    # Current top performers (limited set)
    current = [
        {"symbol": "AAA", "sector": "Technology", "mtd": 0.1},
        {"symbol": "BBB", "sector": "Healthcare", "mtd": 0.05}
    ]
    
    # Historical top performers (different stocks)
    historical = [
        [{"symbol": "CCC", "sector": "Technology", "mtd": 0.15}],  # Last month
        [{"symbol": "DDD", "sector": "Finance", "mtd": 0.12}],    # 2 months ago
    ]
    
    # Full current dataset with data for historical candidates
    current_dataset = [
        {"symbol": "AAA", "sector": "Technology", "mtd": 0.1},
        {"symbol": "BBB", "sector": "Healthcare", "mtd": 0.05},
        {"symbol": "CCC", "sector": "Technology", "mtd": 0.02},  # Now performing poorly
        {"symbol": "DDD", "sector": "Finance", "mtd": 0.08},     # Still performing well
    ]
    
    rows = score_rotation_candidates(
        current,
        historical,
        ["Technology"],
        [{"symbol": "AAA"}],
        current_dataset,
    )
    
    # Should include all unique symbols from current + historical
    symbols = [row["symbol"] for row in rows]
    assert "AAA" in symbols, "Current performer AAA should be included"
    assert "BBB" in symbols, "Current performer BBB should be included"
    assert "CCC" in symbols, "Historical performer CCC should be included"
    assert "DDD" in symbols, "Historical performer DDD should be included"
    
    # CCC should have current data from current_dataset, not historical
    ccc_row = next(row for row in rows if row["symbol"] == "CCC")
    assert ccc_row["mtd"] == 0.02, "CCC should use current data (0.02), not historical (0.15)"
