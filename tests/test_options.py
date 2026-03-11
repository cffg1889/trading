"""
Unit tests for the options recommender.
"""

import math
import pytest
import pandas as pd

from recommender.options import (
    bs_call, bs_put, implied_vol_from_atr, recommend, OptionsRecommendation
)
from patterns.base import Signal


# ── Black-Scholes formulas ────────────────────────────────────────────────────

class TestBlackScholes:
    def test_call_deep_itm(self):
        """Deep ITM call ≈ S - K * e^(-rT)."""
        price = bs_call(S=200.0, K=100.0, T=1.0, r=0.05, sigma=0.2)
        assert price > 95.0   # intrinsic value is 100, time value adds more

    def test_call_atm_positive(self):
        price = bs_call(S=100.0, K=100.0, T=0.25, r=0.05, sigma=0.2)
        assert price > 0.0

    def test_call_expired_intrinsic_value(self):
        """At expiry (T=0), call = max(S-K, 0)."""
        assert bs_call(100.0, 90.0, 0.0, 0.05, 0.2) == pytest.approx(10.0)
        assert bs_call(100.0, 110.0, 0.0, 0.05, 0.2) == pytest.approx(0.0)

    def test_put_call_parity(self):
        """C - P = S - K*e^(-rT)."""
        S, K, T, r, sigma = 100.0, 100.0, 0.5, 0.05, 0.25
        C = bs_call(S, K, T, r, sigma)
        P = bs_put(S, K, T, r, sigma)
        parity = S - K * math.exp(-r * T)
        assert C - P == pytest.approx(parity, rel=1e-6)

    def test_put_deep_otm_near_zero(self):
        price = bs_put(S=200.0, K=50.0, T=0.1, r=0.05, sigma=0.2)
        assert price < 0.01

    def test_call_increases_with_sigma(self):
        """Higher volatility → higher call price."""
        c1 = bs_call(100.0, 100.0, 0.25, 0.05, 0.1)
        c2 = bs_call(100.0, 100.0, 0.25, 0.05, 0.5)
        assert c2 > c1


class TestImpliedVolFromATR:
    def test_lower_bound(self):
        """IV should never be below 5%."""
        iv = implied_vol_from_atr(0.0)
        assert iv == pytest.approx(0.05)

    def test_upper_bound(self):
        """IV should never exceed 200%."""
        iv = implied_vol_from_atr(100.0)
        assert iv == pytest.approx(2.0)

    def test_typical_value(self):
        """1% daily ATR → ~15.9% annualised IV."""
        iv = implied_vol_from_atr(0.01)
        assert 0.14 < iv < 0.18


# ── recommend() ──────────────────────────────────────────────────────────────

def _make_signal(direction: str = "long", confidence: float = 70.0) -> Signal:
    entry = 100.0
    if direction == "long":
        stop, target = 95.0, 115.0
    else:
        stop, target = 105.0, 85.0
    return Signal(
        ticker="TEST", pattern="test", direction=direction,
        timeframe="daily", detected_at=pd.Timestamp.now(tz="UTC"),
        entry=entry, stop=stop, target=target, confidence=confidence,
    )


class TestRecommend:
    def test_long_signal_gives_call(self):
        sig = _make_signal("long")
        rec = recommend(sig, 100.0, 0.02)
        assert rec.option_type == "call"

    def test_short_signal_gives_put(self):
        sig = _make_signal("short")
        rec = recommend(sig, 100.0, 0.02)
        assert rec.option_type == "put"

    def test_high_confidence_outright(self):
        """Confidence >= 65 → outright, no spread."""
        sig = _make_signal(confidence=75.0)
        rec = recommend(sig, 100.0, 0.02)
        assert rec.short_strike is None
        assert rec.max_gain is None   # unlimited

    def test_low_confidence_spread(self):
        """Confidence < 50 → vertical spread."""
        sig = _make_signal(confidence=40.0)
        rec = recommend(sig, 100.0, 0.02)
        assert rec.short_strike is not None
        assert rec.max_gain is not None   # capped

    def test_returns_options_recommendation(self):
        sig = _make_signal()
        rec = recommend(sig, 100.0, 0.02)
        assert isinstance(rec, OptionsRecommendation)

    def test_premium_positive(self):
        sig = _make_signal()
        rec = recommend(sig, 100.0, 0.02)
        assert rec.estimated_premium > 0.0

    def test_max_loss_equals_premium_for_outright(self):
        sig = _make_signal(confidence=70.0)
        rec = recommend(sig, 100.0, 0.02)
        assert rec.max_loss == pytest.approx(rec.estimated_premium, rel=1e-6)

    def test_summary_contains_structure(self):
        sig = _make_signal()
        rec = recommend(sig, 100.0, 0.02)
        assert rec.structure in rec.summary.lower() or rec.structure.upper() in rec.summary

    def test_daily_dte_range(self):
        """Daily signals → DTE between 21 and 45 days."""
        sig = _make_signal(confidence=70.0)
        sig.timeframe = "daily"
        rec = recommend(sig, 100.0, 0.02)
        assert rec.dte in (21, 30)

    def test_intraday_dte(self):
        sig = _make_signal()
        sig.timeframe = "intraday"
        rec = recommend(sig, 100.0, 0.02)
        assert rec.dte == 7
