"""
Orchestrator Agent — runs all sub-agents, aggregates signals,
computes weighted conviction score, and generates the final recommendation.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, WEIGHTS, TICKER, COMPANY
from data.price import get_current_price
from data import store
from agents import technical, news, fundamental, analyst, social

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SIGNAL_SCORES = {
    "STRONG BUY":   2.0,
    "BUY":          1.0,
    "bullish":      1.0,
    "improving":    0.5,
    "neutral":      0.0,
    "flat":         0.0,
    "HOLD":         0.0,
    "deteriorating":-0.5,
    "bearish":     -1.0,
    "SELL":        -1.0,
    "STRONG SELL": -2.0,
}

CONVICTION_LABELS = {
    (1.2,  2.1): ("STRONG BUY",  "#00c851"),
    (0.4,  1.2): ("BUY",         "#4caf50"),
    (-0.4, 0.4): ("HOLD",        "#ffa500"),
    (-1.2,-0.4): ("SELL",        "#f44336"),
    (-2.1,-1.2): ("STRONG SELL", "#b71c1c"),
}


def _score(signal: str) -> float:
    return SIGNAL_SCORES.get(signal, SIGNAL_SCORES.get(
        signal.upper() if signal else "", 0.0))


def _conviction_label(score: float) -> tuple[str, str]:
    for (low, high), (label, color) in CONVICTION_LABELS.items():
        if low <= score < high:
            return label, color
    return "HOLD", "#ffa500"


def run(force_all: bool = False) -> dict:
    """
    Run all agents sequentially and produce the final daily summary.
    Returns the full aggregated result dict.
    """
    quote = get_current_price()

    print("[Orchestrator] Running Technical Agent...")
    tech_result  = technical.run()

    print("[Orchestrator] Running News Agent...")
    news_result  = news.run()

    print("[Orchestrator] Running Fundamental Agent...")
    fund_result  = fundamental.run()

    print("[Orchestrator] Running Analyst Agent...")
    anal_result  = analyst.run()

    print("[Orchestrator] Running Social Agent...")
    soc_result   = social.run()

    # ── Weighted conviction score ─────────────────────────────────────────────
    raw_score = (
        _score(tech_result.get("signal", "HOLD"))  * WEIGHTS["technical"]   +
        _score(fund_result.get("signal", "HOLD"))  * WEIGHTS["fundamental"] +
        _score(news_result.get("signal", "neutral"))* WEIGHTS["news"]       +
        _score(anal_result.get("signal", "neutral"))* WEIGHTS["analyst"]    +
        _score(soc_result.get("signal",  "neutral"))* WEIGHTS["social"]
    )
    conviction, color = _conviction_label(raw_score)

    # ── Final Claude recommendation ───────────────────────────────────────────
    prompt = f"""You are the Chief Investment Officer of a major hedge fund.
You hold a large position in {COMPANY} ({TICKER}) at current price ${quote.get('price', 'N/A')}.

Your analyst team has produced the following assessments:

TECHNICAL:   {tech_result.get('signal','N/A')} (confidence {tech_result.get('confidence','N/A')}%)
  → {tech_result.get('narrative','')}

FUNDAMENTAL: {fund_result.get('signal','N/A')} (confidence {fund_result.get('confidence','N/A')}%)
  → {fund_result.get('narrative','')}

NEWS:        Sentiment {news_result.get('sentiment','N/A')} ({news_result.get('bullish',0)} bullish, {news_result.get('bearish',0)} bearish)
  → {news_result.get('narrative','')}

ANALYST:     {anal_result.get('signal','N/A')} ({anal_result.get('upgrades',0)} upgrades, {anal_result.get('downgrades',0)} downgrades)
  → {anal_result.get('narrative','')}

SOCIAL:      {soc_result.get('signal','N/A')} (exec posts)
  → {soc_result.get('narrative','')}

OVERALL CONVICTION: {conviction} (weighted score: {raw_score:.2f})

Write a concise, actionable recommendation (3-5 sentences) addressed directly to the large shareholder.
Be specific: should they BUY more, HOLD, REDUCE, or EXIT? What price levels matter?
What are the 2 most important things to watch this week?"""

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    recommendation = resp.content[0].text.strip()

    # Key events list (high-impact news + analyst actions)
    key_events = []
    for item in news_result.get("top_items", [])[:3]:
        key_events.append({
            "type":      "news",
            "title":     item.get("title",""),
            "sentiment": item.get("sentiment",""),
            "source":    item.get("source",""),
        })
    for rating in anal_result.get("recent_ratings", [])[:2]:
        key_events.append({
            "type":   "analyst",
            "title":  f"{rating.get('firm','')} {rating.get('action','')} → {rating.get('new_rating','')}",
            "target": rating.get("new_target",""),
        })

    summary = {
        "conviction":        conviction,
        "conviction_color":  color,
        "conviction_score":  round(raw_score, 3),
        "recommendation":    recommendation,
        "key_events":        key_events,
        "technical_view":    tech_result.get("narrative",""),
        "fundamental_view":  fund_result.get("narrative",""),
        "news_view":         news_result.get("narrative",""),
        "analyst_view":      anal_result.get("narrative",""),
        "social_view":       soc_result.get("narrative",""),
        "full_narrative":    recommendation,
        # Sub-agent full results (for dashboard detail)
        "technical":         tech_result,
        "news":              news_result,
        "fundamental":       fund_result,
        "analyst":           anal_result,
        "social":            soc_result,
        "quote":             quote,
    }

    store.save_daily_summary(summary)
    print(f"[Orchestrator] Done. Conviction: {conviction} ({raw_score:.2f})")
    return summary
