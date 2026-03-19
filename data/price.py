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
from scipy.signal import argrelextrema
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
    df["sma200"] = SMAIndicator(df["close"], window=200).sma_indicator()
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


def get_channel_lines(df: pd.DataFrame) -> list:
    """
    Detect multiple price channels at different time scales.
    Returns a list of channel dicts, each ready to draw on the chart.

    Method: connect the 2 MOST EXTREME swing highs → upper line,
            connect the 2 MOST EXTREME swing lows  → lower line.
    This mirrors how a trader draws channels by hand on a chart.
    """
    channels = []

    # ── Channel 1: Sep–Nov 2025 selloff only ──────────────────────────────
    # Slice: from ~130 bars ago (mid-Sep) to ~85 bars ago (late Nov)
    # Does NOT extend beyond that window — stays anchored to that period only
    sep_nov_slice = df.iloc[-130:-82].copy()
    ch1 = _fit_channel(sep_nov_slice, lookback=len(sep_nov_slice), order=6,
                       label="Sep–Nov Channel",
                       color_upper="rgba(80,180,255,0.90)",
                       color_lower="rgba(80,180,255,0.90)",
                       fill="rgba(80,180,255,0.04)",
                       extend=False)
    if ch1:
        channels.append(ch1)

    # ── Channel 2: Jan 16 → Mar 13 2026 ──────────────────────────────────
    jan_mar_slice = df.loc["2026-01-16":"2026-03-18"].copy()
    ch2 = _fit_channel(jan_mar_slice, lookback=len(jan_mar_slice), order=4,
                       label="Jan–Mar Channel",
                       color_upper="rgba(255,180,60,0.90)",
                       color_lower="rgba(255,180,60,0.90)",
                       fill="rgba(255,180,60,0.04)",
                       extend=False)
    if ch2:
        channels.append(ch2)

    return channels


def _fit_channel(df: pd.DataFrame, lookback: int, order: int,
                 label: str, color_upper: str, color_lower: str,
                 fill: str, extend: bool = True) -> dict | None:
    """
    Fit one TRUE PARALLEL channel over the last `lookback` bars.

    Step 1 — Upper line: connect the 2 most prominent swing HIGHS → defines slope.
    Step 2 — Lower line: SAME slope, shifted down to touch the lowest swing LOW.
              This guarantees perfectly parallel lines, like a real price channel.
    Lines are extended 15% beyond the last bar to show projection.
    """
    recent = df.tail(lookback).copy()
    n = len(recent)
    if n < order * 3:
        return None

    high_vals = recent["high"].values
    low_vals  = recent["low"].values
    dates     = recent.index

    hi_idx = argrelextrema(high_vals, np.greater, order=order)[0]
    lo_idx = argrelextrema(low_vals,  np.less,    order=order)[0]

    if len(hi_idx) < 2 or len(lo_idx) < 2:
        return None

    # ── Step 1: Upper line through the 2 HIGHEST swing highs ─────
    # Special case: if the window's absolute high is at bar 0 (first bar),
    # argrelextrema misses it — force it as anchor1 and use the best
    # detected swing high as anchor2.
    first_bar_is_peak = (int(np.argmax(high_vals)) == 0)
    if first_bar_is_peak and len(hi_idx) >= 1:
        x1h = 0
        y1h = float(high_vals[0])
        # Best remaining swing high (highest detected)
        x2h = int(hi_idx[np.argmax(high_vals[hi_idx])])
        y2h = float(high_vals[x2h])
        if x2h == x1h and len(hi_idx) > 1:
            x2h = int(hi_idx[np.argsort(high_vals[hi_idx])[-2]])
            y2h = float(high_vals[x2h])
    else:
        top2 = hi_idx[np.argsort(high_vals[hi_idx])[-2:]]
        top2 = np.sort(top2)                     # chronological order
        x1h, x2h = int(top2[0]), int(top2[1])
        y1h, y2h = float(high_vals[x1h]), float(high_vals[x2h])

    slope = (y2h - y1h) / (x2h - x1h)          # slope defined by two highs

    # ── Step 2: Lower line — SAME slope, anchored at deepest low ─
    # Find the lowest swing low that sits BELOW the upper line at that bar
    best_lo_idx, best_offset = None, 0.0
    for li in lo_idx:
        upper_at_li = y1h + slope * (li - x1h)
        offset = low_vals[li] - upper_at_li      # negative = below upper line
        if offset < best_offset:
            best_offset = offset
            best_lo_idx = li

    if best_lo_idx is None:
        # Fallback: use the absolute minimum low
        best_lo_idx = int(np.argmin(low_vals))
        upper_at_lo = y1h + slope * (best_lo_idx - x1h)
        best_offset = float(low_vals[best_lo_idx]) - upper_at_lo

    # Lower line = upper line shifted down by best_offset
    # y_lower(x) = y_upper(x) + best_offset
    intercept_upper = y1h - slope * x1h
    intercept_lower = intercept_upper + best_offset

    # ── Project lines: from first high anchor → end (+ optional extension) ─
    ext       = int(n * 0.15) if extend else 0
    x_start   = x1h                             # start at first anchor high
    x_end     = n - 1 + ext

    uy_start  = slope * x_start + intercept_upper
    uy_end    = slope * x_end   + intercept_upper
    ly_start  = slope * x_start + intercept_lower
    ly_end    = slope * x_end   + intercept_lower

    last_date  = dates[-1]
    ext_date   = last_date + pd.tseries.offsets.BDay(ext) if extend else last_date
    start_date = dates[x_start]

    direction = "descending" if slope < 0 else "ascending"

    return {
        "label":        label,
        "color_upper":  color_upper,
        "color_lower":  color_lower,
        "fill":         fill,
        "direction":    direction,
        "upper_x":      [start_date, ext_date],
        "upper_y":      [uy_start,   uy_end],
        "lower_x":      [start_date, ext_date],
        "lower_y":      [ly_start,   ly_end],
        # Dots at the anchor swing highs used to define the slope
        "anchor_hi_x":  [dates[x1h], dates[x2h]],
        "anchor_hi_y":  [y1h,         y2h],
        # Dot at the anchor low that set the channel width
        "anchor_lo_x":  [dates[best_lo_idx]],
        "anchor_lo_y":  [float(low_vals[best_lo_idx])],
    }


def get_short_interest() -> dict:
    """
    Fetch short interest for BX and persist every data point to SQLite.

    Strategy:
    - yfinance gives us current snapshot + prior month (2 points)
    - Both are stored in db/bx.db on every run
    - All stored history is returned for the chart
    - Over time this builds up a proper time-series (new FINRA data ≈ every 2 weeks)
    """
    import sqlite3, os

    db_path = os.path.join(os.path.dirname(__file__), "..", "db", "bx.db")
    db_path = os.path.abspath(db_path)

    # ── Ensure table exists ───────────────────────────────────────
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS short_interest (
            date        TEXT PRIMARY KEY,
            pct_float   REAL,
            shares_short INTEGER,
            days_to_cover REAL,
            source      TEXT
        )
    """)
    conn.commit()

    # ── Fetch from yfinance ───────────────────────────────────────
    ticker   = yf.Ticker(config.TICKER)
    info     = ticker.info
    float_sh = info.get("floatShares") or 1

    cur_pct    = (info.get("shortPercentOfFloat") or 0) * 100
    cur_shares = info.get("sharesShort") or 0
    days_cover = info.get("shortRatio") or 0
    cur_date   = pd.Timestamp(info.get("dateShortInterest") or 0, unit="s").normalize()
    if cur_date.year < 2020:                         # fallback if timestamp bad
        cur_date = pd.Timestamp.now().normalize()

    prior_shares = info.get("sharesShortPriorMonth") or 0
    prior_ts     = info.get("sharesShortPreviousMonthDate") or 0
    prior_pct    = (prior_shares / float_sh * 100) if float_sh else 0
    prior_date   = pd.Timestamp(prior_ts, unit="s").normalize() if prior_ts else None

    # ── Upsert both points ────────────────────────────────────────
    rows_to_save = [(cur_date, cur_pct, cur_shares, days_cover, "yfinance_current")]
    if prior_date and prior_date != cur_date:
        rows_to_save.append((prior_date, prior_pct, prior_shares, 0, "yfinance_prior"))

    for date, pct, shares, dtc, src in rows_to_save:
        conn.execute("""
            INSERT INTO short_interest (date, pct_float, shares_short, days_to_cover, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                pct_float     = excluded.pct_float,
                shares_short  = excluded.shares_short,
                days_to_cover = excluded.days_to_cover
        """, (date.strftime("%Y-%m-%d"), round(pct, 4),
              int(shares), round(dtc, 2), src))
    conn.commit()

    # ── Read full history from DB ─────────────────────────────────
    rows = conn.execute(
        "SELECT date, pct_float, days_to_cover FROM short_interest ORDER BY date"
    ).fetchall()
    conn.close()

    dates      = [pd.Timestamp(r[0]) for r in rows]
    values     = [round(r[1], 2)     for r in rows]
    dtc_latest = rows[-1][2] if rows else days_cover

    return {
        "current_pct":   round(cur_pct, 2),
        "prior_pct":     round(prior_pct, 2),
        "days_to_cover": round(dtc_latest, 1),
        "dates":         dates,
        "values":        values,
    }


def get_realized_volatility(df: pd.DataFrame, window: int = 30) -> pd.Series:
    """
    Compute annualised 30-day rolling realized volatility from daily close prices.
    Formula: std(log returns, window=30) * sqrt(252) * 100  → percentage.
    This gives a full daily time series and is a natural benchmark for IV.
    """
    log_ret = np.log(df["close"] / df["close"].shift(1))
    rv = log_ret.rolling(window).std() * np.sqrt(252) * 100
    return rv.dropna()


def get_implied_volatility() -> dict:
    """
    Compute BX 30-day constant-maturity ATM implied volatility from options chain.
    Persists each daily reading to SQLite and returns full history for the chart.

    Method: interpolate between the two expirations that bracket 30 calendar days
    to produce a single 30-day IV number, matching how market makers quote vol.
    """
    import sqlite3, os

    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db", "bx.db"))
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS implied_vol (
            date      TEXT PRIMARY KEY,
            iv_30d    REAL,
            iv_near   REAL,
            atm_strike REAL
        )
    """)
    conn.commit()

    try:
        ticker   = yf.Ticker(config.TICKER)
        price    = ticker.fast_info.last_price
        exps     = ticker.options            # tuple of expiration date strings

        # ── Collect ATM IV for each of the first 6 expirations ───
        exp_data = []
        today    = pd.Timestamp.now().normalize()
        for exp in exps[:6]:
            days = (pd.Timestamp(exp) - today).days
            if days < 1:
                continue
            chain    = ticker.option_chain(exp)
            atm      = chain.calls.iloc[
                (chain.calls["strike"] - price).abs().argsort()[:1]
            ]
            atm_str  = float(atm["strike"].values[0])
            c_iv     = chain.calls[chain.calls["strike"] == atm_str]["impliedVolatility"].values
            p_iv     = chain.puts[chain.puts["strike"]   == atm_str]["impliedVolatility"].values
            iv_vals  = [v for v in [*c_iv, *p_iv] if v > 0.01]
            if iv_vals:
                exp_data.append((days, float(np.mean(iv_vals)) * 100, atm_str))

        if not exp_data:
            raise ValueError("No valid options data")

        # ── Interpolate to 30-day constant maturity ───────────────
        exp_data.sort()
        near_iv = exp_data[0][1]
        atm_str = exp_data[0][2]

        # Find two expirations bracketing 30 days
        below = [(d, iv) for d, iv, _ in exp_data if d <= 30]
        above = [(d, iv) for d, iv, _ in exp_data if d >  30]

        if below and above:
            d1, iv1 = below[-1]
            d2, iv2 = above[0]
            # Linear interpolation
            iv_30d = iv1 + (iv2 - iv1) * (30 - d1) / (d2 - d1)
        elif above:
            iv_30d = above[0][1]
        else:
            iv_30d = below[-1][1]

        iv_30d = round(iv_30d, 2)

        # ── Persist today's reading ───────────────────────────────
        today_str = today.strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO implied_vol (date, iv_30d, iv_near, atm_strike)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                iv_30d    = excluded.iv_30d,
                iv_near   = excluded.iv_near,
                atm_strike = excluded.atm_strike
        """, (today_str, iv_30d, round(near_iv, 2), atm_str))
        conn.commit()

    except Exception as e:
        print(f"[IV] fetch error: {e}")
        iv_30d  = 0.0
        near_iv = 0.0
        atm_str = 0.0

    # ── Read full history ─────────────────────────────────────────
    rows = conn.execute(
        "SELECT date, iv_30d FROM implied_vol ORDER BY date"
    ).fetchall()
    conn.close()

    dates  = [pd.Timestamp(r[0]) for r in rows]
    values = [r[1] for r in rows]

    return {
        "iv_30d":  iv_30d,
        "iv_near": near_iv,
        "dates":   dates,
        "values":  values,
    }


def get_hourly_rsi(window: int = 14) -> pd.Series:
    """
    Fetch 60-day 1H OHLCV for BX and return the RSI-14 series on hourly bars.
    Identical Wilder method to the daily RSI — only the bar interval differs.
    This matches exactly what Saxo Bank shows on their 1H chart.
    """
    ticker = yf.Ticker(config.TICKER)
    df_h = ticker.history(period="60d", interval="1h", auto_adjust=True)
    if df_h.empty:
        return pd.Series(dtype=float)
    df_h.index = pd.to_datetime(df_h.index, utc=True).tz_convert("America/New_York")
    close = df_h["Close"]
    rsi_h = RSIIndicator(close, window=window).rsi()
    return rsi_h.dropna()


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
