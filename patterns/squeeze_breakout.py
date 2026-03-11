"""
Pattern 5 — Volatility Squeeze Breakout (TTM Squeeze)

A "squeeze" occurs when Bollinger Bands narrow inside Keltner Channels.
This indicates a period of volatility compression — a coiled spring.
When the squeeze fires (BBs expand outside KCs), momentum explodes.

Logic:
  1. Detect squeeze: BB upper < KC upper AND BB lower > KC lower (for N bars)
  2. Confirm squeeze release: BB now outside KC
  3. Determine direction using a momentum oscillator:
       mom = close - midpoint(high+low+close of last N bars)
  4. Optional: volume expansion at release → confirms move

Confidence boosted by:
  - Longer squeeze duration (more compression = more energy)
  - Higher volume at release
  - Momentum histogram increasing vs prior bar (acceleration)
  - Trend alignment (above/below SMA50)
"""

from __future__ import annotations
import pandas as pd
import numpy as np

from .base import PatternDetector, Signal
from config import STOP_ATR_MULT, TARGET_ATR_MULT


class SqueezeBreakoutDetector(PatternDetector):
    name = "Volatility Squeeze Breakout"

    MIN_SQUEEZE_BARS = 5   # minimum consecutive squeeze bars
    MOM_PERIOD       = 12  # momentum lookback

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        required = ["bb_upper", "bb_lower", "kc_upper", "kc_lower", "atr"]
        if len(df) < 30 or not all(c in df.columns for c in required):
            return []

        signals: list[Signal] = []

        bb_u = df["bb_upper"]
        bb_l = df["bb_lower"]
        kc_u = df["kc_upper"]
        kc_l = df["kc_lower"]

        # Squeeze = BB inside KC
        in_squeeze = (bb_u < kc_u) & (bb_l > kc_l)

        # Count consecutive squeeze bars ending at bar[-2]
        squeeze_count = 0
        for i in range(len(df) - 2, max(len(df) - 40, 0), -1):
            if in_squeeze.iloc[i]:
                squeeze_count += 1
            else:
                break

        if squeeze_count < self.MIN_SQUEEZE_BARS:
            return []

        # Squeeze just fired: previous bar was in squeeze, current bar is not
        currently_in_squeeze = bool(in_squeeze.iloc[-1])
        was_in_squeeze        = bool(in_squeeze.iloc[-2])

        if not (was_in_squeeze and not currently_in_squeeze):
            return []

        # ── Momentum direction ────────────────────────────────────────────────
        lookback = df.iloc[-self.MOM_PERIOD - 1:]
        delta    = lookback["High"] - lookback["Low"]
        mid_hl   = (lookback["High"].rolling(self.MOM_PERIOD).max()
                   + lookback["Low"].rolling(self.MOM_PERIOD).min()) / 2
        mom      = (lookback["Close"] - (mid_hl + lookback["Close"].rolling(self.MOM_PERIOD).mean()) / 2)
        mom_last = float(mom.iloc[-1])
        mom_prev = float(mom.iloc[-2]) if len(mom) >= 2 else 0.0

        last_close = float(df["Close"].iloc[-1])
        atr_val    = float(df["atr"].iloc[-1])
        vol_ratio  = float(df["vol_ratio"].iloc[-1]) if "vol_ratio" in df.columns else 1.0

        # ── Bullish: positive and growing momentum ────────────────────────────
        if mom_last > 0:
            score = 50.0
            score += min(squeeze_count / 20, 1.0) * 20   # longer squeeze → up to +20
            if mom_last > mom_prev:
                score += 10   # momentum accelerating
            if vol_ratio >= 1.5:
                score += 10
            if "sma50" in df.columns and last_close > float(df["sma50"].iloc[-1]):
                score += 5
            score = max(0.0, min(100.0, score))

            stop   = last_close - STOP_ATR_MULT   * atr_val
            target = last_close + TARGET_ATR_MULT * atr_val

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "Bullish Squeeze Breakout",
                direction   = "long",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(last_close, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"Squeeze={squeeze_count} bars mom={mom_last:.4f}",
            ))

        # ── Bearish: negative and falling momentum ────────────────────────────
        elif mom_last < 0:
            score = 50.0
            score += min(squeeze_count / 20, 1.0) * 20
            if mom_last < mom_prev:
                score += 10
            if vol_ratio >= 1.5:
                score += 10
            if "sma50" in df.columns and last_close < float(df["sma50"].iloc[-1]):
                score += 5
            score = max(0.0, min(100.0, score))

            stop   = last_close + STOP_ATR_MULT   * atr_val
            target = last_close - TARGET_ATR_MULT * atr_val

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "Bearish Squeeze Breakout",
                direction   = "short",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(last_close, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"Squeeze={squeeze_count} bars mom={mom_last:.4f}",
            ))

        return signals
