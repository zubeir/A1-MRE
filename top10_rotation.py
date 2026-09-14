"""Quantitative scoring for the A1-MRE Top-10 momentum sleeve."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence


SIGNAL_INVEST = "Invest"
SIGNAL_HOLD = "Hold / Watch"
SIGNAL_DROP = "Drop"


def _symbol(record: Mapping) -> str | None:
    value = record.get("symbol", record.get("Ticker"))
    return str(value).strip().upper() if value is not None and str(value).strip() else None


def _normalise_sector(value) -> str:
    return str(value or "").strip().casefold()


def calculate_persistence(cohorts: Sequence[Iterable], max_months: int = 6) -> dict[str, dict[str, int]]:
    """Count unique cohort appearances and normalize them to 0-100.

    ``cohorts`` is ordered newest-first. Duplicate symbols within one cohort count
    once, which keeps malformed/raw lists from inflating persistence.
    """
    usable = list(cohorts or [])[:max_months]
    counts: dict[str, int] = {}
    for cohort in usable:
        seen = set()
        for record in cohort or []:
            symbol = _symbol(record) if isinstance(record, Mapping) else str(record).strip().upper()
            if symbol and symbol not in seen:
                counts[symbol] = counts.get(symbol, 0) + 1
                seen.add(symbol)
    denominator = max(len(usable), 1)
    return {
        symbol: {
            "appearance_count_6m": count,
            "appearance_score": int(round(count / denominator * 100)),
        }
        for symbol, count in counts.items()
    }


def classify_mtd(mtd) -> tuple[str, int]:
    """Return the required Green/Yellow/Red label and score."""
    try:
        value = float(mtd)
    except (TypeError, ValueError):
        value = 0.0
    if value > 0:
        return "Green", 100
    if value < 0:
        return "Red", 0
    return "Yellow", 50


def _signal(score: float) -> str:
    if score >= 70:
        return SIGNAL_INVEST
    if score >= 40:
        return SIGNAL_HOLD
    return SIGNAL_DROP


def _get_breakout_symbols(breakout_records) -> set[str]:
    if isinstance(breakout_records, Mapping):
        symbols = {_symbol({"symbol": key}) for key in breakout_records}
        symbols.update(_symbol(value) for value in breakout_records.values() if isinstance(value, Mapping))
    else:
        symbols = {_symbol(value) for value in (breakout_records or [])}
    symbols.discard(None)
    return symbols


def _score_candidate(record, persistence, aligned_sectors, breakout_symbols) -> dict:
    row = dict(record)
    symbol = _symbol(row) or ""
    appearance = persistence.get(symbol, {"appearance_count_6m": 1, "appearance_score": 0})
    mtd_status, mtd_score = classify_mtd(row.get("mtd"))
    sector_aligned = _normalise_sector(row.get("sector")) in aligned_sectors
    breakout = symbol in breakout_symbols
    rotation_score = round(
        0.4 * appearance["appearance_score"] + 0.3 * mtd_score
        + 0.2 * (100 if sector_aligned else 0) + 0.1 * (100 if breakout else 0), 2
    )
    row.update({
        "appearance_count_6m": appearance["appearance_count_6m"],
        "appearance_score": appearance["appearance_score"],
        "mtd_status": mtd_status,
        "mtd_score": mtd_score,
        "sector_aligned": sector_aligned,
        "sector_score": 100 if sector_aligned else 0,
        "breakout_52w_high": breakout,
        "breakout_score": 100 if breakout else 0,
        "rotation_score": rotation_score,
        "rotation_signal": _signal(rotation_score),
    })
    return row


def score_rotation_candidates(
    current_candidates: Sequence[Mapping],
    historical_cohorts: Sequence[Iterable],
    top_sector_leaders: Sequence[str] | None = None,
    breakout_records: Iterable[Mapping] | Mapping | None = None,
    current_dataset: Sequence[Mapping] | None = None,
) -> list[dict]:
    """Score and rank rotation candidates using the four-factor model.

    Candidates are drawn from the union of current top performers and all stocks
    that have appeared in historical top 10 lists. The current cohort is included
    as the newest persistence cohort. Pass up to five prior cohorts in
    ``historical_cohorts`` to form the six-month window.
    
    Args:
        current_candidates: Current top performers (used for persistence calculation)
        historical_cohorts: Prior monthly top 10 lists
        top_sector_leaders: Top performing sectors for sector alignment scoring
        breakout_records: Stocks showing 52-week high breakouts
        current_dataset: Optional broader dataset with current data for all stocks.
                        If provided, historical candidates will be evaluated using
                        their current data from this dataset.
    """
    current = list(current_candidates or [])
    
    # Build lookup for current dataset if provided
    current_data_lookup = {}
    if current_dataset:
        current_data_lookup = {_symbol(record): record for record in current_dataset if _symbol(record)}
    
    # Create pool of all unique stocks from current and historical cohorts
    all_candidates = {}
    
    # Add current candidates with their full data
    for record in current:
        symbol = _symbol(record)
        if symbol:
            all_candidates[symbol] = record
    
    # Add historical candidates, preferring current dataset data when available
    for cohort in historical_cohorts or []:
        for record in cohort or []:
            symbol = _symbol(record)
            if symbol and symbol not in all_candidates:
                # Prefer current dataset data if available, otherwise use historical data
                if symbol in current_data_lookup:
                    all_candidates[symbol] = current_data_lookup[symbol]
                else:
                    # Use historical data if current data not available
                    all_candidates[symbol] = record
    
    # Calculate persistence using current top performers + historical cohorts
    persistence = calculate_persistence([current, *(historical_cohorts or [])], 6)
    aligned_sectors = {_normalise_sector(value) for value in (top_sector_leaders or [])}
    breakout_symbols = _get_breakout_symbols(breakout_records)
    
    # Score all candidates in the pool
    scored = [_score_candidate(row, persistence, aligned_sectors, breakout_symbols) for row in all_candidates.values()]
    return sorted(scored, key=lambda row: (-float(row["rotation_score"]), _symbol(row) or ""))


def select_rotation_tickers(scored_candidates: Sequence[Mapping], limit: int = 10) -> list[dict]:
    """Select Invest rows first, then highest-scoring fallback rows."""
    ranked = [dict(row) for row in scored_candidates]
    invests = [row for row in ranked if row.get("rotation_signal") == SIGNAL_INVEST]
    selected = invests[:limit]
    selected_symbols = {_symbol(row) for row in selected}
    selected.extend(row for row in ranked if _symbol(row) not in selected_symbols and len(selected) < limit)
    return selected[:limit]


def record_rotation_confirmation(selected: Sequence[Mapping], allocation_mode: str, path: str) -> None:
    """Append a confirmed rotation to a small JSON history log."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            history = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    history.append({
        "confirmed_at_utc": datetime.now(timezone.utc).isoformat(),
        "allocation_mode": allocation_mode,
        "tickers": [_symbol(row) for row in selected if _symbol(row)],
        "scores": {(_symbol(row) or ""): row.get("rotation_score") for row in selected if _symbol(row)},
    })
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)
