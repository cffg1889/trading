"""
Fundamental Analysis Agent — powered by Claude.
Evaluates BX financials, valuation, dividend, and peer comparison.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, TICKER, COMPANY
from data.price import get_fundamentals, get_peers_performance
from data import store

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run() -> dict:
    """Run fundamental analysis. Returns structured result."""
    fund  = get_fundamentals()
    peers = get_peers_performance()

    peers_str = ""
    if not peers.empty:
        peers_str = "\n".join(
            f"  {row['ticker']}: {row['1mo_return']:+.2f}%"
            for _, row in peers.iterrows()
        )

    prompt = f"""You are a top-tier fundamental analyst specialising in alternative asset managers.
Analyse {COMPANY} ({TICKER}) based on the following data.

=== VALUATION ===
Trailing P/E:   {fund.get('pe_ratio', 'N/A')}
Forward P/E:    {fund.get('forward_pe', 'N/A')}
Price/Book:     {fund.get('price_to_book', 'N/A')}

=== INCOME ===
Revenue:        ${fund.get('revenue', 0):,}
Net Income:     ${fund.get('net_income', 0):,}
Profit Margin:  {(fund.get('profit_margin') or 0)*100:.1f}%
ROE:            {(fund.get('roe') or 0)*100:.1f}%

=== DIVIDEND ===
Dividend Yield: {(fund.get('dividend_yield') or 0)*100:.2f}%
Annual Payout:  ${fund.get('dividend_rate', 'N/A')}

=== RISK ===
Beta: {fund.get('beta', 'N/A')}
Short % Float: {(fund.get('short_pct_float') or 0)*100:.1f}%

=== 1-MONTH RELATIVE PERFORMANCE ===
{peers_str if peers_str else 'No peer data available'}

=== ANALYST CONSENSUS ===
# Analysts:   {fund.get('analyst_count', 'N/A')}
Target Mean:  ${fund.get('target_mean', 'N/A')}
Target High:  ${fund.get('target_high', 'N/A')}
Target Low:   ${fund.get('target_low', 'N/A')}
Consensus:    {fund.get('recommendation', 'N/A')}

Key context: Blackstone is an alternative asset manager. Key metrics are AUM growth,
fee-related earnings (FRE), distributable earnings (DE), and dividend growth.
It is particularly sensitive to interest rates and private market valuations.

Respond ONLY with valid JSON:
{{
  "signal": "STRONG BUY|BUY|HOLD|SELL|STRONG SELL",
  "confidence": 0-100,
  "valuation": "cheap|fair|expensive",
  "dividend_health": "strong|stable|at_risk",
  "peer_performance": "outperforming|in-line|underperforming",
  "upside_to_target": percentage to mean analyst target,
  "key_strengths": [list up to 3],
  "key_risks": [list up to 3],
  "narrative": "3-4 sentence institutional analysis"
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response.content[0].text)
    except Exception:
        text  = response.content[0].text
        start = text.find("{")
        end   = text.rfind("}") + 1
        result = json.loads(text[start:end])

    store.save_fundamentals({
        "data":      fund,
        "narrative": result.get("narrative"),
        "signal":    result.get("signal"),
    })

    result["raw_data"] = fund
    return result
