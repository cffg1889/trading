"""
Market data fetcher with local Parquet cache.

Usage:
    from data.fetcher import get_ohlcv
    df = get_ohlcv("AAPL", timeframe="daily")
"""

from __future__ import annotations
import time
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from config import CACHE_DIR, TIMEFRAMES, CACHE_EXPIRY_HOURS

logger = logging.getLogger(__name__)


def _cache_path(ticker: str, timeframe: str) -> Path:
    key = hashlib.md5(f"{ticker}_{timeframe}".encode()).hexdigest()[:8]
    safe = ticker.replace("/", "_").replace("=", "_").replace("^", "_")
    return CACHE_DIR / f"{safe}_{timeframe}_{key}.parquet"


def _is_cache_valid(path: Path, timeframe: str) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    expiry_hours = CACHE_EXPIRY_HOURS.get(timeframe, 24)
    return datetime.now() - mtime < timedelta(hours=expiry_hours)


def get_ohlcv(
    ticker: str,
    timeframe: str = "daily",
    force_refresh: bool = False,
    period: str | None = None,
) -> pd.DataFrame | None:
    """
    Fetch OHLCV data for a ticker.

    Returns a DataFrame with columns:
        Open, High, Low, Close, Volume
    Indexed by datetime (UTC-aware).

    Args:
        period: Override the default period (e.g. "5y" for backtest history).
                When set, bypasses the cache (result is not cached).

    Returns None if data cannot be fetched.
    """
    params = TIMEFRAMES.get(timeframe)
    if params is None:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Choose from {list(TIMEFRAMES)}")

    effective_period = period or params["period"]

    # Only use cache when fetching the default period
    if period is None:
        cache_file = _cache_path(ticker, timeframe)
        if not force_refresh and _is_cache_valid(cache_file, timeframe):
            try:
                df = pd.read_parquet(cache_file)
                logger.debug(f"[cache hit]  {ticker} ({timeframe})")
                return df
            except Exception as e:
                logger.warning(f"[cache read error] {ticker}: {e}")
    else:
        cache_file = None

    try:
        raw = yf.download(
            ticker,
            period=effective_period,
            interval=params["interval"],
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as e:
        logger.warning(f"[fetch error] {ticker}: {e}")
        return None

    if raw is None or raw.empty:
        logger.debug(f"[no data]    {ticker} ({timeframe})")
        return None

    # Flatten MultiIndex columns produced by yfinance ≥ 0.2.x
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Keep only OHLCV
    cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    df = raw[cols].copy()
    df.dropna(subset=["Close"], inplace=True)

    if df.empty:
        return None

    # Ensure tz-aware index
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    try:
        if cache_file is not None:
            df.to_parquet(cache_file)
            logger.debug(f"[cached]     {ticker} ({timeframe})")
    except Exception as e:
        logger.warning(f"[cache write error] {ticker}: {e}")

    return df


def get_ohlcv_batch(
    tickers: list[str],
    timeframe: str = "daily",
    force_refresh: bool = False,
    max_retries: int = 2,
    delay_between: float = 0.1,
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV for multiple tickers sequentially with retry logic.
    Returns {ticker: DataFrame} for successful fetches only.
    """
    results: dict[str, pd.DataFrame] = {}

    for idx, ticker in enumerate(tickers):
        for attempt in range(max_retries + 1):
            df = get_ohlcv(ticker, timeframe=timeframe, force_refresh=force_refresh)
            if df is not None:
                results[ticker] = df
                break
            if attempt < max_retries:
                time.sleep(delay_between * (attempt + 1))

        if idx < len(tickers) - 1:
            time.sleep(delay_between)

    return results


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add commonly needed technical indicators to an OHLCV DataFrame.
    Uses the 'ta' library; falls back to manual computation if unavailable.

    Added columns:
        atr, atr_pct,
        rsi,
        bb_upper, bb_mid, bb_lower, bb_width,
        kc_upper, kc_lower,
        vwap,
        vol_sma20,  vol_ratio,
        sma20, sma50, sma200,
        ema9, ema21,
    """
    df = df.copy()
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"] if "Volume" in df.columns else pd.Series(0, index=df.index)

    # ── ATR ──────────────────────────────────────────────────────────────────
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"]     = tr.ewm(span=14, adjust=False).mean()
    df["atr_pct"] = df["atr"] / close

    # ── RSI ───────────────────────────────────────────────────────────────────
    delta  = close.diff()
    gain   = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss   = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
    rs     = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - 100 / (1 + rs)

    # ── Bollinger Bands (20, 2σ) ───────────────────────────────────────────────
    sma20          = close.rolling(20).mean()
    std20          = close.rolling(20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_mid"]   = sma20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20

    # ── Keltner Channels (20, 1.5 × ATR) ─────────────────────────────────────
    df["kc_upper"] = sma20 + 1.5 * df["atr"]
    df["kc_lower"] = sma20 - 1.5 * df["atr"]

    # ── VWAP (rolling daily proxy — sum(price×vol) / sum(vol)) ───────────────
    if vol.sum() > 0:
        pv = ((high + low + close) / 3) * vol
        df["vwap"] = pv.rolling(20).sum() / vol.rolling(20).sum()
    else:
        df["vwap"] = (high + low + close) / 3

    # ── Volume indicators ─────────────────────────────────────────────────────
    df["vol_sma20"] = vol.rolling(20).mean()
    df["vol_ratio"] = vol / df["vol_sma20"].replace(0, float("nan"))

    # ── Moving averages ───────────────────────────────────────────────────────
    df["sma20"]  = sma20
    df["sma50"]  = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["ema9"]   = close.ewm(span=9,  adjust=False).mean()
    df["ema21"]  = close.ewm(span=21, adjust=False).mean()

    return df
