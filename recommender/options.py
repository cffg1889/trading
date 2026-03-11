"""
Options trade recommender.

Given a Signal, recommends:
  - Call or Put (based on direction)
  - Strike (ATM, OTM, or spread depending on confidence)
  - Maturity (days to expiry) — chosen to match expected move duration
  - Structure: outright long option OR vertical spread
  - Estimated premium using Black-Scholes
  - Max loss / max gain for risk disclosure

Black-Scholes via the 'mibian' library (no API key required).
Falls back to simplified BS formula if mibian is unavailable.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional

from patterns.base import Signal
from config import DEFAULT_RISK_FREE_RATE, OPTIONS_MATURITIES

# ── Black-Scholes helpers (no external dependency) ───────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European call price."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def bs_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European put price (via put-call parity)."""
    call = bs_call(S, K, T, r, sigma)
    return call - S + K * math.exp(-r * T)


def implied_vol_from_atr(atr_pct: float) -> float:
    """
    Rough implied volatility estimate from ATR%.
    Annualised: IV ≈ ATR% × sqrt(252)
    """
    return min(max(atr_pct * math.sqrt(252), 0.05), 2.0)


# ── Trade recommendation ───────────────────────────────────────────────────────

@dataclass
class OptionsRecommendation:
    signal:         Signal
    option_type:    str      # "call" | "put"
    structure:      str      # "long call" | "long put" | "bull call spread" | "bear put spread"
    strike:         float
    long_strike:    float
    short_strike:   Optional[float]   # only for spreads
    dte:            int      # days to expiry
    estimated_premium: float
    max_loss:       float
    max_gain:       float    # capped for spreads
    iv_used:        float

    @property
    def summary(self) -> str:
        spread_str = ""
        if self.short_strike:
            spread_str = f"/ {self.short_strike:.2f} spread"
        return (
            f"  ▶ {self.structure.upper()}  "
            f"Strike {self.long_strike:.2f}{spread_str}  "
            f"Exp ~{self.dte}d  "
            f"Premium ~{self.estimated_premium:.2f}  "
            f"MaxLoss {self.max_loss:.2f}  MaxGain {self.max_gain:.2f}  "
            f"(IV {self.iv_used*100:.0f}%)"
        )


def recommend(
    signal: Signal,
    current_price: float,
    atr_pct: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> OptionsRecommendation:
    """
    Build an options trade recommendation for a given signal.

    Strategy selection:
      - confidence < 60  → vertical spread (defined risk, lower cost)
      - confidence ≥ 60  → outright long option

    Maturity selection:
      - daily timeframe    → 21–45 days
      - hourly timeframe   → 7–14 days
      - intraday timeframe → 7 days
    """
    S     = current_price
    iv    = implied_vol_from_atr(atr_pct)
    r     = risk_free_rate

    # ── Choose maturity ───────────────────────────────────────────────────────
    tf = signal.timeframe
    if tf == "daily":
        dte = 21 if signal.confidence >= 70 else 30
    elif tf == "hourly":
        dte = 14
    else:
        dte = 7
    T = dte / 365.0

    is_long  = signal.direction == "long"
    opt_type = "call" if is_long else "put"

    # ── Strike selection ──────────────────────────────────────────────────────
    # ATM-ish, rounded to nearest 0.5 or 1.0 depending on price magnitude
    rounding = 1.0 if S >= 10 else 0.5
    atm_strike = round(S / rounding) * rounding

    # For high confidence: ATM outright
    # For lower confidence: slightly OTM outright or spread
    if signal.confidence >= 65:
        long_K = atm_strike
        use_spread = False
    elif signal.confidence >= 50:
        otm_offset = round(atr_pct * S * 0.5 / rounding) * rounding
        long_K = (atm_strike + otm_offset) if is_long else (atm_strike - otm_offset)
        use_spread = False
    else:
        # Vertical spread: buy ATM, sell 1-target away
        long_K     = atm_strike
        move       = abs(signal.target - signal.entry)
        short_K    = (long_K + round(move / rounding) * rounding) if is_long \
                     else (long_K - round(move / rounding) * rounding)
        use_spread = True

    # ── Premium calculation ───────────────────────────────────────────────────
    if is_long:
        long_premium = bs_call(S, long_K, T, r, iv)
    else:
        long_premium = bs_put(S, long_K, T, r, iv)

    if use_spread:
        short_K_val = short_K
        if is_long:
            short_premium = bs_call(S, short_K_val, T, r, iv)
        else:
            short_premium = bs_put(S, short_K_val, T, r, iv)
        net_premium = long_premium - short_premium
        spread_width = abs(short_K_val - long_K)
        max_gain = spread_width - net_premium
        max_loss = net_premium
        structure = "bull call spread" if is_long else "bear put spread"
    else:
        short_K_val = None
        net_premium = long_premium
        max_loss    = net_premium
        max_gain    = float("inf")   # unlimited for outright
        structure   = f"long {opt_type}"

    return OptionsRecommendation(
        signal            = signal,
        option_type       = opt_type,
        structure         = structure,
        strike            = long_K,
        long_strike       = long_K,
        short_strike      = short_K_val,
        dte               = dte,
        estimated_premium = round(net_premium, 4),
        max_loss          = round(max_loss, 4),
        max_gain          = round(max_gain, 4) if max_gain != float("inf") else 999999.0,
        iv_used           = round(iv, 4),
    )
