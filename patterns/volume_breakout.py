"""
Pattern 2 — Volume-Confirmed Breakout

Logic:
  - Price breaks above N-day high (or below N-day low)
  - Volume on breakout bar ≥ 1.5× 20-day average (mandatory)
  - Price was consolidating (low BB width) before the break → squeeze
  - Confidence boosted by:
      * the higher the vol_ratio, the better
      * BB width compression before breakout (tighter = more explosive)
      * trend alignment: price above/below SMA50
      * no failed breakout in recent N bars
"""

from __future__ import annotations
import pandas as pd
import numpy as np

from .base import PatternDetector, Signal
from config import STOP_ATR_MULT, TARGET_ATR_MULT, BREAKOUT_VOL_MULT


class VolumeBreakoutDetector(PatternDetector):
    name = "Volume-Confirmed Breakout"

    LOOKBACK_HIGH   = 20    # N-day high/low
    MIN_VOL_RATIO   = BREAKOUT_VOL_MULT
    BB_SQUEEZE_PCT  = 0.04  # BB width < 4% of price → consolidation

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        required = ["bb_width", "vol_ratio", "atr", "sma50"]
        if len(df) < self.LOOKBACK_HIGH + 5 or not all(c in df.columns for c in required):
            return []

        signals: list[Signal] = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        close      = float(last["Close"])
        vol_ratio  = float(last["vol_ratio"]) if not pd.isna(last["vol_ratio"]) else 0.0
        atr_val    = float(last["atr"])
        bb_width   = float(last["bb_width"]) if not pd.isna(last["bb_width"]) else 1.0

        # Volume must be above threshold
        if vol_ratio < self.MIN_VOL_RATIO:
            return []

        lookback = df.iloc[-(self.LOOKBACK_HIGH + 1):-1]
        high_n   = float(lookback["High"].max())
        low_n    = float(lookback["Low"].min())

        # ── Bullish breakout ──────────────────────────────────────────────────
        if float(last["High"]) > high_n and float(prev["Close"]) <= high_n:
            entry   = close
            stop    = close - STOP_ATR_MULT   * atr_val
            target  = close + TARGET_ATR_MULT * atr_val

            score = 50.0
            score += min(vol_ratio - self.MIN_VOL_RATIO, 3.0) * 10   # up to +30 for vol
            if bb_width < self.BB_SQUEEZE_PCT:
                score += 15   # tight squeeze before breakout
            if "sma50" in df.columns and close > float(last["sma50"]):
                score += 5    # trend alignment

            score = max(0.0, min(100.0, score))

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "Bullish Volume Breakout",
                direction   = "long",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(entry, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"{self.LOOKBACK_HIGH}d high={high_n:.4f} vol×{vol_ratio:.1f}",
            ))

        # ── Bearish breakdown ─────────────────────────────────────────────────
        if float(last["Low"]) < low_n and float(prev["Close"]) >= low_n:
            entry   = close
            stop    = close + STOP_ATR_MULT   * atr_val
            target  = close - TARGET_ATR_MULT * atr_val

            score = 50.0
            score += min(vol_ratio - self.MIN_VOL_RATIO, 3.0) * 10
            if bb_width < self.BB_SQUEEZE_PCT:
                score += 15
            if "sma50" in df.columns and close < float(last["sma50"]):
                score += 5

            score = max(0.0, min(100.0, score))

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "Bearish Volume Breakdown",
                direction   = "short",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(entry, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"{self.LOOKBACK_HIGH}d low={low_n:.4f} vol×{vol_ratio:.1f}",
            ))

        return signals
