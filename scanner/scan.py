"""
Main scanner — runs all pattern detectors across the universe in parallel.

Usage:
    from scanner.scan import run_scan
    results = run_scan(timeframe="daily", max_workers=8)
"""

from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import pandas as pd

from data.universe import get_universe, get_flat_universe
from data.fetcher   import get_ohlcv, add_indicators
from config        import BACKTEST_PERIOD
from patterns       import ALL_DETECTORS
from patterns.base  import Signal
from backtest.engine import run_backtest, BacktestResult
from backtest.cache  import load as bt_cache_load, save as bt_cache_save
from recommender.options import recommend
from config import TOP_N_SIGNALS

logger = logging.getLogger(__name__)


# ── Per-ticker worker ─────────────────────────────────────────────────────────

def _process_ticker(
    ticker: str,
    timeframe: str,
    run_bt: bool,
    backtest_stride: int = 1,
) -> list[dict]:
    """
    Fetch data, run all detectors, optionally backtest, build trade recommendations.
    Returns a list of result dicts (one per signal).
    """
    df = get_ohlcv(ticker, timeframe=timeframe)
    if df is None or len(df) < 30:
        return []

    df = add_indicators(df)
    results = []

    for DetectorClass in ALL_DETECTORS:
        detector = DetectorClass()
        try:
            signals = detector.detect(ticker, df, timeframe)
        except Exception as e:
            logger.debug(f"[scan] {ticker} {detector.name}: {e}")
            continue

        # ── Backtest once per detector (not once per signal) ──────────────────
        bt_result: BacktestResult | None = None
        if run_bt and signals:
            cached = bt_cache_load(ticker, detector.name, timeframe)
            if cached:
                bt_result = BacktestResult(**cached)
            else:
                # For daily scans, try to fetch a longer history for backtest
                df_bt = df
                if timeframe == "daily":
                    df_long = get_ohlcv(ticker, timeframe=timeframe, period=BACKTEST_PERIOD)
                    if df_long is not None and len(df_long) >= 60:
                        df_bt = add_indicators(df_long)
                if len(df_bt) >= 60:
                    bt_result = run_backtest(detector, ticker, df_bt, timeframe,
                                             stride=backtest_stride)
                    if bt_result:
                        # Save without raw trades to keep cache files small
                        cache_data = {**bt_result.__dict__, "trades": []}
                        bt_cache_save(ticker, detector.name, timeframe, cache_data)

        for sig in signals:
            # Attach backtest stats to signal
            if bt_result and bt_result.n_trades > 0:
                sig.win_rate  = bt_result.win_rate
                sig.avg_rr    = bt_result.avg_rr
                sig.n_samples = bt_result.n_trades

            # Options recommendation
            atr_pct = float(df["atr_pct"].iloc[-1]) if "atr_pct" in df.columns else 0.02
            try:
                opt_rec = recommend(sig, sig.entry, atr_pct)
            except Exception as e:
                logger.debug(f"[options] {ticker}: {e}")
                opt_rec = None

            results.append({
                "signal":    sig,
                "bt_result": bt_result,
                "opt_rec":   opt_rec,
            })

    return results


# ── Main scan ─────────────────────────────────────────────────────────────────

def run_scan(
    timeframe:   str  = "daily",
    max_workers: int  = 8,
    run_backtest_flag: bool = True,
    categories:  list[str] | None = None,
    top_n:       int  = TOP_N_SIGNALS,
    include_commodities: bool = False,
    backtest_stride: int = 1,
) -> list[dict]:
    """
    Scan the full universe and return top_n signals sorted by confidence.

    Args:
        timeframe:            "daily" | "hourly" | "intraday"
        max_workers:          parallelism level
        run_backtest_flag:    compute historical win rates (slower)
        categories:           limit to specific universe categories
        top_n:                max signals to return
        include_commodities:  add GC, CL, NG… to the scan
        backtest_stride:      check every N bars in walk-forward (1=every bar)
    """
    universe = get_universe(include_commodities=include_commodities)
    if categories:
        tickers = []
        for cat in categories:
            tickers.extend(universe.get(cat, []))
    else:
        tickers = get_flat_universe(include_commodities=include_commodities)

    logger.info(f"Scanning {len(tickers)} instruments ({timeframe}) with {max_workers} workers…")

    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_ticker, t, timeframe, run_backtest_flag, backtest_stride): t
            for t in tickers
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Scanning"):
            ticker = futures[future]
            try:
                res = future.result(timeout=30)
                all_results.extend(res)
            except Exception as e:
                logger.debug(f"[scan] {ticker}: {e}")

    # Sort by confidence descending
    all_results.sort(key=lambda x: x["signal"].confidence, reverse=True)
    return all_results[:top_n]
