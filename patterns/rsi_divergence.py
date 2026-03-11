"""
Pattern 3 — RSI Divergence (Regular + Hidden)

Regular Bullish Divergence:  price makes lower low, RSI makes higher low  → reversal up
Regular Bearish Divergence:  price makes higher high, RSI makes lower high → reversal down

Hidden Bullish Divergence:   price makes higher low (pullback in uptrend), RSI makes lower low → continuation up
Hidden Bearish Divergence:   price makes lower high (rally in downtrend),  RSI makes higher high → continuation down

Confidence boosted by:
  - RSI in oversold (<35) or overbought (>65) zone
  - Divergence over longer time span
  - Trend alignment for hidden divergences
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import PatternDetector, Signal
from config import STOP_ATR_MULT, TARGET_ATR_MULT, RSI_OVERSOLD, RSI_OVERBOUGHT


class RSIDivergenceDetector(PatternDetector):
    name = "RSI Divergence"

    LOOKBACK = 50
    ORDER    = 4    # local extrema order
    RSI_MIN_DIFF = 3.0   # minimum RSI difference to count as divergence

    def detect(self, ticker: str, df: pd.DataFrame, timeframe: str = "daily") -> list[Signal]:
        if len(df) < self.LOOKBACK + 10 or "rsi" not in df.columns:
            return []

        signals: list[Signal] = []
        window = df.iloc[-self.LOOKBACK:]
        close  = window["Close"].values
        rsi    = window["rsi"].values
        atr    = self._atr(df)

        # Pivot lows
        low_idx  = argrelextrema(close, np.less,    order=self.ORDER)[0]
        # Pivot highs
        high_idx = argrelextrema(close, np.greater, order=self.ORDER)[0]

        last_close = float(df["Close"].iloc[-1])
        atr_val    = float(atr.iloc[-1])

        # ── Regular Bullish: price LL, RSI HL ────────────────────────────────
        if len(low_idx) >= 2:
            i1, i2 = low_idx[-2], low_idx[-1]
            price_ll = close[i2] < close[i1]
            rsi_hl   = rsi[i2]   > rsi[i1] + self.RSI_MIN_DIFF

            if price_ll and rsi_hl:
                score  = 55.0
                if rsi[i2] < RSI_OVERSOLD:
                    score += 20
                span   = i2 - i1
                score += min(span / self.LOOKBACK * 20, 15)  # longer divergence = better
                score  = max(0.0, min(100.0, score))

                stop   = close[i2] - STOP_ATR_MULT * atr_val
                target = last_close + TARGET_ATR_MULT * atr_val

                signals.append(Signal(
                    ticker      = ticker,
                    pattern     = "Regular Bullish Divergence (RSI)",
                    direction   = "long",
                    timeframe   = timeframe,
                    detected_at = df.index[-1],
                    entry       = round(last_close, 4),
                    stop        = round(stop, 4),
                    target      = round(target, 4),
                    confidence  = round(score, 1),
                    notes       = (f"Price lows {close[i1]:.4f}→{close[i2]:.4f} "
                                   f"RSI {rsi[i1]:.1f}→{rsi[i2]:.1f}"),
                ))

        # ── Regular Bearish: price HH, RSI LH ────────────────────────────────
        if len(high_idx) >= 2:
            i1, i2 = high_idx[-2], high_idx[-1]
            price_hh = close[i2] > close[i1]
            rsi_lh   = rsi[i2]   < rsi[i1] - self.RSI_MIN_DIFF

            if price_hh and rsi_lh:
                score  = 55.0
                if rsi[i2] > RSI_OVERBOUGHT:
                    score += 20
                span   = i2 - i1
                score += min(span / self.LOOKBACK * 20, 15)
                score  = max(0.0, min(100.0, score))

                stop   = close[i2] + STOP_ATR_MULT * atr_val
                target = last_close - TARGET_ATR_MULT * atr_val

                signals.append(Signal(
                    ticker      = ticker,
                    pattern     = "Regular Bearish Divergence (RSI)",
                    direction   = "short",
                    timeframe   = timeframe,
                    detected_at = df.index[-1],
                    entry       = round(last_close, 4),
                    stop        = round(stop, 4),
                    target      = round(target, 4),
                    confidence  = round(score, 1),
                    notes       = (f"Price highs {close[i1]:.4f}→{close[i2]:.4f} "
                                   f"RSI {rsi[i1]:.1f}→{rsi[i2]:.1f}"),
                ))

        # ── Hidden Bullish: price HL (uptrend pullback), RSI LL ──────────────
        if len(low_idx) >= 2 and "sma50" in df.columns:
            i1, i2  = low_idx[-2], low_idx[-1]
            price_hl = close[i2] > close[i1]   # higher low = pullback in uptrend
            rsi_ll   = rsi[i2]   < rsi[i1] - self.RSI_MIN_DIFF

            # Confirm uptrend: close above SMA50
            sma50_last = float(df["sma50"].iloc[-1])
            in_uptrend = last_close > sma50_last

            if price_hl and rsi_ll and in_uptrend:
                score  = 50.0
                if rsi[i2] < RSI_OVERSOLD:
                    score += 15
                score  = max(0.0, min(100.0, score))

                stop   = close[i2] - STOP_ATR_MULT * atr_val
                target = last_close + TARGET_ATR_MULT * atr_val

                signals.append(Signal(
                    ticker      = ticker,
                    pattern     = "Hidden Bullish Divergence (RSI)",
                    direction   = "long",
                    timeframe   = timeframe,
                    detected_at = df.index[-1],
                    entry       = round(last_close, 4),
                    stop        = round(stop, 4),
                    target      = round(target, 4),
                    confidence  = round(score, 1),
                    notes       = (f"Price lows {close[i1]:.4f}→{close[i2]:.4f} (higher) "
                                   f"RSI {rsi[i1]:.1f}→{rsi[i2]:.1f} (lower)"),
                ))

        return signals
