"""
Technical Analysis Agent — powered by Claude.
Analyses price data, indicators, patterns and generates a structured signal.
"""
import json
import anthropic
import numpy as np
from scipy.signal import argrelextrema
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, TICKER
from data.price import get_ohlcv, get_current_price, get_options_data
from data.scrapers.finviz import get_short_interest
from data import store

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _find_support_resistance(df, order: int = 10) -> tuple[list, list]:
    closes = df["close"].values
    highs  = df["high"].values
    lows   = df["low"].values

    local_max_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    local_min_idx = argrelextrema(lows,  np.less_equal,   order=order)[0]

    resistances = sorted(set(round(float(highs[i]), 2) for i in local_max_idx[-8:]))
    supports    = sorted(set(round(float(lows[i]),  2) for i in local_min_idx[-8:]))

    return supports, resistances


def _detect_patterns(df) -> list[str]:
    patterns = []
    closes = df["close"]
    last   = closes.iloc[-1]

    # Death cross / golden cross
    if df["ma50"].iloc[-1] < df["ma200"].iloc[-1] and df["ma50"].iloc[-5] >= df["ma200"].iloc[-5]:
        patterns.append("Death Cross (50MA crossed below 200MA)")
    if df["ma50"].iloc[-1] > df["ma200"].iloc[-1] and df["ma50"].iloc[-5] <= df["ma200"].iloc[-5]:
        patterns.append("Golden Cross (50MA crossed above 200MA)")

    # Price vs MAs
    if last < df["ma200"].iloc[-1]:
        patterns.append("Trading below 200-day MA (bearish long-term)")
    if last < df["ma50"].iloc[-1]:
        patterns.append("Trading below 50-day MA (bearish medium-term)")
    if last < df["ma20"].iloc[-1]:
        patterns.append("Trading below 20-day MA (bearish short-term)")

    # Bollinger squeeze / breakout
    bb_width_now  = df["bb_upper"].iloc[-1] - df["bb_lower"].iloc[-1]
    bb_width_prev = df["bb_upper"].iloc[-20] - df["bb_lower"].iloc[-20]
    if bb_width_now < bb_width_prev * 0.7:
        patterns.append("Bollinger Band squeeze (low volatility, breakout pending)")
    if last < df["bb_lower"].iloc[-1]:
        patterns.append("Price below lower Bollinger Band (oversold / breakdown)")
    if last > df["bb_upper"].iloc[-1]:
        patterns.append("Price above upper Bollinger Band (overbought / breakout)")

    # RSI conditions
    rsi = df["rsi"].iloc[-1]
    if rsi < 30:
        patterns.append(f"RSI oversold ({rsi:.1f})")
    elif rsi > 70:
        patterns.append(f"RSI overbought ({rsi:.1f})")

    # MACD crossover
    if (df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] and
            df["macd"].iloc[-2] <= df["macd_signal"].iloc[-2]):
        patterns.append("MACD bullish crossover")
    if (df["macd"].iloc[-1] < df["macd_signal"].iloc[-1] and
            df["macd"].iloc[-2] >= df["macd_signal"].iloc[-2]):
        patterns.append("MACD bearish crossover")

    # Volume surge
    if df["vol_ratio"].iloc[-1] > 2.0:
        patterns.append(f"Volume surge ({df['vol_ratio'].iloc[-1]:.1f}x average)")

    return patterns


def run() -> dict:
    """Run full technical analysis and save to DB. Returns structured result."""
    df = get_ohlcv(period="1y", interval="1d")
    if df.empty:
        return {"error": "No price data"}

    quote     = get_current_price()
    options   = get_options_data()
    short_int = get_short_interest()
    supports, resistances = _find_support_resistance(df)
    patterns  = _detect_patterns(df)

    last      = df.iloc[-1]
    price     = quote.get("price", float(last["close"]))
    rsi       = round(float(last["rsi"]), 1)
    macd      = round(float(last["macd"]), 3)
    macd_sig  = round(float(last["macd_signal"]), 3)
    atr       = round(float(last["atr"]), 2)
    vol_ratio = round(float(last["vol_ratio"]), 2)
    ma20      = round(float(last["ma20"]), 2)
    ma50      = round(float(last["ma50"]), 2)
    ma200     = round(float(last["ma200"]), 2)
    bb_upper  = round(float(last["bb_upper"]), 2)
    bb_lower  = round(float(last["bb_lower"]), 2)

    # 5-day and 20-day returns
    ret5d  = round((price / float(df["close"].iloc[-5]) - 1) * 100, 2)
    ret20d = round((price / float(df["close"].iloc[-20]) - 1) * 100, 2)

    prompt = f"""You are an elite institutional technical analyst at a top hedge fund.
Analyse Blackstone Inc ({TICKER}) with the following data and provide a professional assessment.

=== CURRENT MARKET DATA ===
Price:       ${price}
Change 5d:   {ret5d}%
Change 20d:  {ret20d}%
52W High:    ${quote.get('week52_high', 'N/A')}
52W Low:     ${quote.get('week52_low', 'N/A')}

=== TECHNICAL INDICATORS ===
RSI(14):            {rsi}
MACD:               {macd}  |  Signal: {macd_sig}
ATR(14):            ${atr}
Volume vs 20d avg:  {vol_ratio}x
20-day MA:   ${ma20}
50-day MA:   ${ma50}
200-day MA:  ${ma200}
Bollinger Upper: ${bb_upper}
Bollinger Lower: ${bb_lower}

=== KEY LEVELS ===
Nearest supports:    {supports[-4:] if supports else 'N/A'}
Nearest resistances: {resistances[:4] if resistances else 'N/A'}

=== DETECTED PATTERNS ===
{chr(10).join(f'- {p}' for p in patterns) if patterns else '- No strong patterns detected'}

=== SHORT INTEREST ===
Short Float:  {short_int.get('short_float', 'N/A')}
Short Ratio:  {short_int.get('short_ratio', 'N/A')} days to cover
Inst. Ownership: {short_int.get('inst_own', 'N/A')}

=== OPTIONS FLOW ===
Put/Call Ratio: {options.get('put_call_ratio', 'N/A')}
Nearest Expiry: {options.get('expiry', 'N/A')}
Call OI: {options.get('call_oi', 'N/A')}
Put OI:  {options.get('put_oi', 'N/A')}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "trend": "Strong Uptrend|Uptrend|Neutral|Downtrend|Strong Downtrend",
  "signal": "STRONG BUY|BUY|HOLD|SELL|STRONG SELL",
  "confidence": 0-100,
  "key_support": [price levels as numbers],
  "key_resistance": [price levels as numbers],
  "stop_loss": suggested stop loss price,
  "price_target": near-term price target,
  "patterns": [list of pattern names],
  "narrative": "3-4 sentence institutional quality analysis",
  "risk_reward": "brief risk/reward assessment"
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response.content[0].text)
    except json.JSONDecodeError:
        text = response.content[0].text
        start = text.find("{")
        end   = text.rfind("}") + 1
        result = json.loads(text[start:end])

    result["period"]    = "1y"
    result["support"]   = result.pop("key_support",   supports[-4:])
    result["resistance"]= result.pop("key_resistance", resistances[:4])
    result["raw_data"]  = {
        "price": price, "rsi": rsi, "macd": macd, "ma20": ma20,
        "ma50": ma50, "ma200": ma200, "atr": atr, "vol_ratio": vol_ratio,
        "short_float": short_int.get("short_float"),
        "put_call_ratio": options.get("put_call_ratio"),
    }

    store.save_technical(result)
    return result
