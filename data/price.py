"""
Price data and technical indicators for BX using yfinance.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD, SMAIndicator, IchimokuIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
import config


def get_price_data(period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data for BX and compute all technical indicators."""
    ticker = yf.Ticker(config.TICKER)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {config.TICKER}")

    df.index = pd.to_datetime(df.index)
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume"
    })

    # ── Trend indicators ──────────────────────────────────────────
    df["ema20"]  = EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"]  = EMAIndicator(df["close"], window=50).ema_indicator()
    df["sma200"] = SMAIndicator(df["close"], window=200).simple_moving_average()
    df["ema9"]   = EMAIndicator(df["close"], window=9).ema_indicator()

    # ── Bollinger Bands ───────────────────────────────────────────
    bb = BollingerBands(df["close"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"]   = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    df["bb_pct"]   = bb.bollinger_pband()

    # ── RSI ───────────────────────────────────────────────────────
    df["rsi"] = RSIIndicator(df["close"], window=14).rsi()

    # ── MACD ──────────────────────────────────────────────────────
    macd = MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"]   = macd.macd_diff()

    # ── Stochastic ────────────────────────────────────────────────
    stoch = StochasticOscillator(df["high"], df["low"], df["close"], window=14, smooth_window=3)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # ── ATR ───────────────────────────────────────────────────────
    df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()

    # ── Volume indicators ─────────────────────────────────────────
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma20"]
    df["obv"] = OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()

    # ── VWAP (rolling 20-day) ─────────────────────────────────────
    df["vwap"] = (df["close"] * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()

    # ── Support / Resistance (local extrema) ─────────────────────
    df["support"]    = _find_support(df)
    df["resistance"] = _find_resistance(df)

    # ── Price change ──────────────────────────────────────────────
    df["pct_change"] = df["close"].pct_change() * 100
    df["pct_change_5d"] = df["close"].pct_change(5) * 100

    return df.dropna(subset=["ema20", "rsi"])


def _find_support(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling minimum as a proxy support level."""
    return df["low"].rolling(window, center=True).min()


def _find_resistance(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling maximum as a proxy resistance level."""
    return df["high"].rolling(window, center=True).max()


def get_key_levels(df: pd.DataFrame) -> dict:
    """Identify key price levels for the chart."""
    recent = df.tail(252)  # last year
    current = df["close"].iloc[-1]

    # Find significant pivot lows (support)
    lows = []
    highs = []
    for i in range(10, len(recent) - 10):
        if recent["low"].iloc[i] == recent["low"].iloc[i-10:i+10].min():
            lows.append(recent["low"].iloc[i])
        if recent["high"].iloc[i] == recent["high"].iloc[i-10:i+10].max():
            highs.append(recent["high"].iloc[i])

    # Key supports below current price
    supports = sorted([l for l in lows if l < current], reverse=True)[:3]
    # Key resistances above current price
    resistances = sorted([h for h in highs if h > current])[:3]

    return {
        "current": current,
        "52w_high": df["high"].tail(252).max(),
        "52w_low": df["low"].tail(252).min(),
        "supports": supports,
        "resistances": resistances,
        "atr": df["atr"].iloc[-1],
        "rsi": df["rsi"].iloc[-1],
        "macd": df["macd"].iloc[-1],
        "macd_signal": df["macd_signal"].iloc[-1],
        "bb_upper": df["bb_upper"].iloc[-1],
        "bb_lower": df["bb_lower"].iloc[-1],
        "volume_ratio": df["volume_ratio"].iloc[-1],
    }


def get_current_quote() -> dict:
    """Get real-time quote for BX."""
    ticker = yf.Ticker(config.TICKER)
    info = ticker.fast_info
    hist = ticker.history(period="2d", interval="1d")

    prev_close = hist["Close"].iloc[-2] if len(hist) >= 2 else hist["Close"].iloc[-1]
    current = hist["Close"].iloc[-1]
    change = current - prev_close
    change_pct = (change / prev_close) * 100

    return {
        "price": round(current, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(hist["Volume"].iloc[-1]),
        "prev_close": round(prev_close, 2),
    }
