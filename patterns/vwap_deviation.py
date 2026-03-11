"""
Pattern 4 — VWAP Deviation + Mean Reversion

Logic:
  - Price deviates > N standard deviations from rolling VWAP
  - Volume spike at the extreme (confirms the exhaustion move)
  - RSI in extreme zone (oversold/overbought)
  - Reversion target = VWAP

This pattern is particularly effective on intraday (1h, 15m) but also works
on daily when combined with vol confirmation.

Confidence boosted by:
  - Larger vol spike at extreme
  - RSI further in oversold/overbought zone
  - Price touching/piercing Bollinger Band
"""

from __future__ import annotations
import pandas as pd
import numpy as np

from .base import PatternDetector, Signal
from config import STOP_ATR_MULT, VWAP_STD_THRESHOLD, RSI_OVERSOLD, RSI_OVERBOUGHT


class VWAPDeviationDetector(PatternDetector):
    name = "VWAP Deviation Mean Reversion"

    STD_LOOKBACK = 20
    MIN_VOL_RATIO = 1.3

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        required = ["vwap", "rsi", "atr", "vol_ratio"]
        if len(df) < self.STD_LOOKBACK + 5 or not all(c in df.columns for c in required):
            return []

        signals: list[Signal] = []
        last    = df.iloc[-1]
        close   = float(last["Close"])
        vwap    = float(last["vwap"])    if not pd.isna(last["vwap"])    else None
        rsi     = float(last["rsi"])     if not pd.isna(last["rsi"])     else None
        atr_val = float(last["atr"])
        vol_ratio = float(last["vol_ratio"]) if not pd.isna(last["vol_ratio"]) else 0.0

        if vwap is None or rsi is None:
            return []

        # Compute rolling std of (close - vwap)
        deviation_series = df["Close"] - df["vwap"]
        dev_std = float(deviation_series.rolling(self.STD_LOOKBACK).std().iloc[-1])
        if dev_std == 0 or np.isnan(dev_std):
            return []

        dev_z = (close - vwap) / dev_std  # z-score of current deviation

        # ── Oversold: price too far below VWAP ───────────────────────────────
        if dev_z < -VWAP_STD_THRESHOLD and vol_ratio >= self.MIN_VOL_RATIO:
            score = 50.0
            score += min(abs(dev_z) - VWAP_STD_THRESHOLD, 2.0) * 10   # deeper = better
            if rsi < RSI_OVERSOLD:
                score += 20
            if vol_ratio >= 2.0:
                score += 10
            # BB touch bonus
            if "bb_lower" in df.columns:
                bb_lower = float(last["bb_lower"])
                if close <= bb_lower:
                    score += 10

            score = max(0.0, min(100.0, score))

            entry  = close
            stop   = close - STOP_ATR_MULT * atr_val
            target = vwap   # revert to VWAP

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "VWAP Oversold Deviation",
                direction   = "long",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(entry, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"Dev z={dev_z:.2f} VWAP={vwap:.4f} RSI={rsi:.1f}",
            ))

        # ── Overbought: price too far above VWAP ─────────────────────────────
        if dev_z > VWAP_STD_THRESHOLD and vol_ratio >= self.MIN_VOL_RATIO:
            score = 50.0
            score += min(dev_z - VWAP_STD_THRESHOLD, 2.0) * 10
            if rsi > RSI_OVERBOUGHT:
                score += 20
            if vol_ratio >= 2.0:
                score += 10
            if "bb_upper" in df.columns:
                bb_upper = float(last["bb_upper"])
                if close >= bb_upper:
                    score += 10

            score = max(0.0, min(100.0, score))

            entry  = close
            stop   = close + STOP_ATR_MULT * atr_val
            target = vwap

            signals.append(Signal(
                ticker      = ticker,
                pattern     = "VWAP Overbought Deviation",
                direction   = "short",
                timeframe   = timeframe,
                detected_at = df.index[-1],
                entry       = round(entry, 4),
                stop        = round(stop, 4),
                target      = round(target, 4),
                confidence  = round(score, 1),
                notes       = f"Dev z={dev_z:.2f} VWAP={vwap:.4f} RSI={rsi:.1f}",
            ))

        return signals
