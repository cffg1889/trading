"""
Pattern 1 — Double Bottom / Double Top

Logic:
  - Find two local lows (highs) within a lookback window
  - Both lows within ±3% of each other
  - A "valley peak" between them (neckline)
  - Current close breaks above neckline (or below for double top)
  - Volume on second bottom lower than first (accumulation)  — optional bonus
  - Confidence boosted by:
      * smaller difference between the two lows
      * RSI divergence (second low has higher RSI)
      * volume dry-up on second low
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import PatternDetector, Signal
from config import STOP_ATR_MULT, TARGET_ATR_MULT


class DoubleBottomDetector(PatternDetector):
    name = "Double Bottom / Double Top"

    # ── tuning knobs ──────────────────────────────────────────────────────────
    LOOKBACK   = 60   # bars to scan
    TOL        = 0.04 # two lows must be within 4% of each other
    ORDER      = 5    # argrelextrema order (local min over ±5 bars)

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        if len(df) < self.LOOKBACK + 10:
            return []

        signals: list[Signal] = []
        close = df["Close"]
        atr   = self._atr(df)

        window = df.iloc[-self.LOOKBACK:]
        c = window["Close"].values

        # ── local minima → double bottom ──────────────────────────────────────
        lows_idx = argrelextrema(c, np.less, order=self.ORDER)[0]
        if len(lows_idx) >= 2:
            sig = self._check_double_bottom(
                ticker, df, window, lows_idx, atr, timeframe
            )
            if sig:
                signals.append(sig)

        # ── local maxima → double top ─────────────────────────────────────────
        highs_idx = argrelextrema(c, np.greater, order=self.ORDER)[0]
        if len(highs_idx) >= 2:
            sig = self._check_double_top(
                ticker, df, window, highs_idx, atr, timeframe
            )
            if sig:
                signals.append(sig)

        return signals

    # ── Double Bottom ─────────────────────────────────────────────────────────
    def _check_double_bottom(
        self, ticker, df, window, lows_idx, atr, timeframe
    ) -> Signal | None:
        close  = window["Close"].values
        volume = window["Volume"].values if "Volume" in window.columns else None
        rsi    = window["rsi"].values    if "rsi"    in window.columns else None

        # Take the last two lows in the window
        b1_i, b2_i = lows_idx[-2], lows_idx[-1]
        b1, b2     = close[b1_i], close[b2_i]

        # Lows must be within tolerance
        if abs(b1 - b2) / max(b1, b2) > self.TOL:
            return None

        # Neckline = max close between the two lows
        neckline = close[b1_i:b2_i + 1].max()

        # Breakout: latest close must be above neckline
        last_close = close[-1]
        if last_close <= neckline:
            return None

        # Entry, stop, target
        entry_price = last_close
        atr_val     = float(atr.iloc[-1])
        stop        = min(b1, b2) - STOP_ATR_MULT * atr_val
        target      = neckline + (neckline - min(b1, b2))  # measured move

        # ── Confidence scoring ────────────────────────────────────────────────
        score = 50.0

        # Symmetry: smaller diff → higher score
        pct_diff = abs(b1 - b2) / max(b1, b2)
        score += (1 - pct_diff / self.TOL) * 15  # up to +15

        # RSI divergence: higher RSI on 2nd bottom
        if rsi is not None and not np.isnan(rsi[b1_i]) and not np.isnan(rsi[b2_i]):
            if rsi[b2_i] > rsi[b1_i]:
                score += 15
            elif rsi[b2_i] < rsi[b1_i] - 5:
                score -= 10

        # Volume dry-up on 2nd bottom
        if volume is not None and volume[b1_i] > 0 and volume[b2_i] > 0:
            if volume[b2_i] < volume[b1_i] * 0.85:
                score += 10
            elif volume[b2_i] > volume[b1_i] * 1.2:
                score -= 5

        # Breakout with volume
        if volume is not None and "vol_sma20" in df.columns:
            last_vol_ratio = float(df["vol_ratio"].iloc[-1]) if "vol_ratio" in df.columns else 1.0
            if last_vol_ratio > 1.5:
                score += 10

        score = max(0.0, min(100.0, score))

        return Signal(
            ticker      = ticker,
            pattern     = "Double Bottom",
            direction   = "long",
            timeframe   = timeframe,
            detected_at = df.index[-1],
            entry       = round(entry_price, 4),
            stop        = round(stop, 4),
            target      = round(target, 4),
            confidence  = round(score, 1),
            notes       = f"Neckline={neckline:.4f} B1={b1:.4f} B2={b2:.4f}",
        )

    # ── Double Top ────────────────────────────────────────────────────────────
    def _check_double_top(
        self, ticker, df, window, highs_idx, atr, timeframe
    ) -> Signal | None:
        close  = window["Close"].values
        volume = window["Volume"].values if "Volume" in window.columns else None
        rsi    = window["rsi"].values    if "rsi"    in window.columns else None

        t1_i, t2_i = highs_idx[-2], highs_idx[-1]
        t1, t2     = close[t1_i], close[t2_i]

        if abs(t1 - t2) / max(t1, t2) > self.TOL:
            return None

        neckline   = close[t1_i:t2_i + 1].min()
        last_close = close[-1]

        if last_close >= neckline:
            return None

        entry_price = last_close
        atr_val     = float(atr.iloc[-1])
        stop        = max(t1, t2) + STOP_ATR_MULT * atr_val
        target      = neckline - (max(t1, t2) - neckline)  # measured move

        score = 50.0

        pct_diff = abs(t1 - t2) / max(t1, t2)
        score += (1 - pct_diff / self.TOL) * 15

        if rsi is not None and not np.isnan(rsi[t1_i]) and not np.isnan(rsi[t2_i]):
            if rsi[t2_i] < rsi[t1_i]:
                score += 15
            elif rsi[t2_i] > rsi[t1_i] + 5:
                score -= 10

        if volume is not None and volume[t1_i] > 0 and volume[t2_i] > 0:
            if volume[t2_i] < volume[t1_i] * 0.85:
                score += 10

        score = max(0.0, min(100.0, score))

        return Signal(
            ticker      = ticker,
            pattern     = "Double Top",
            direction   = "short",
            timeframe   = timeframe,
            detected_at = df.index[-1],
            entry       = round(entry_price, 4),
            stop        = round(stop, 4),
            target      = round(target, 4),
            confidence  = round(score, 1),
            notes       = f"Neckline={neckline:.4f} T1={t1:.4f} T2={t2:.4f}",
        )
