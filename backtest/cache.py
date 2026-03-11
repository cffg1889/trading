"""
Backtest result cache — saves/loads BacktestResult objects to JSON
so we don't recompute expensive backtests on every run.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

from config import BASE_DIR

logger = logging.getLogger(__name__)

BT_CACHE_DIR = BASE_DIR / "cache" / "backtest"
BT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
BT_EXPIRY_DAYS = 7   # recompute weekly


def _cache_path(ticker: str, pattern_name: str, timeframe: str) -> Path:
    safe = (ticker + "_" + pattern_name + "_" + timeframe).replace(" ", "_").replace("/", "_")
    return BT_CACHE_DIR / f"{safe}.json"


def load(ticker: str, pattern_name: str, timeframe: str) -> dict | None:
    path = _cache_path(ticker, pattern_name, timeframe)
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    if datetime.now() - mtime > timedelta(days=BT_EXPIRY_DAYS):
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.warning(f"[bt-cache read] {ticker}/{pattern_name}: {e}")
        return None


def save(ticker: str, pattern_name: str, timeframe: str, data: dict) -> None:
    path = _cache_path(ticker, pattern_name, timeframe)
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"[bt-cache write] {ticker}/{pattern_name}: {e}")
