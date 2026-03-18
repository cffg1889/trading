"""
News Agent — scrapes all sources, scores sentiment with Claude,
identifies high-impact items, and saves to DB.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from data.scrapers.rss    import fetch_rss_news
from data.scrapers.edgar  import get_recent_filings, get_insider_transactions
from data.scrapers.wsj    import fetch_wsj_news
from data.scrapers.cnbc   import fetch_cnbc_news
from data import store

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _score_articles(articles: list[dict]) -> list[dict]:
    """Use Claude to batch-score sentiment and impact for news items."""
    if not articles:
        return []

    summaries = "\n".join(
        f'{i+1}. [{a["source"]}] {a["title"]} — {a["summary"][:150]}'
        for i, a in enumerate(articles[:20])
    )

    prompt = f"""You are a senior analyst at a hedge fund covering Blackstone Inc (BX).
Score each news item below for sentiment and impact on BX stock.

{summaries}

Respond ONLY with valid JSON array (one object per item, same order):
[{{"sentiment": "bullish|bearish|neutral", "impact": "high|medium|low",
   "summary": "one sentence summary from institutional perspective"}}]"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text   = response.content[0].text
        start  = text.find("[")
        end    = text.rfind("]") + 1
        scores = json.loads(text[start:end])

        for i, score in enumerate(scores[:len(articles)]):
            articles[i]["sentiment"] = score.get("sentiment", "neutral")
            articles[i]["impact"]    = score.get("impact", "low")
            if score.get("summary"):
                articles[i]["summary"] = score["summary"]
    except Exception as e:
        print(f"[News Agent] Scoring error: {e}")

    return articles


def run() -> dict:
    """Collect all news, score it, save to DB. Return summary."""
    all_articles = []

    # RSS (always available)
    rss = fetch_rss_news()
    all_articles.extend(rss)

    # SEC filings
    filings = get_recent_filings(days=7)
    all_articles.extend(filings)

    insider = get_insider_transactions(days=30)
    all_articles.extend(insider)

    # WSJ (subscriber)
    try:
        wsj = fetch_wsj_news()
        all_articles.extend(wsj)
    except Exception as e:
        print(f"[News Agent] WSJ error: {e}")

    # CNBC (subscriber)
    try:
        cnbc = fetch_cnbc_news()
        all_articles.extend(cnbc)
    except Exception as e:
        print(f"[News Agent] CNBC error: {e}")

    # Score sentiment
    scored = _score_articles(all_articles)

    # Save to DB
    store.save_news(scored)

    # Build summary for orchestrator
    high_impact = [a for a in scored if a.get("impact") == "high"]
    bullish     = sum(1 for a in scored if a.get("sentiment") == "bullish")
    bearish     = sum(1 for a in scored if a.get("sentiment") == "bearish")
    total       = len(scored)

    sentiment_balance = "neutral"
    if total > 0:
        if bullish / total > 0.6:
            sentiment_balance = "bullish"
        elif bearish / total > 0.5:
            sentiment_balance = "bearish"

    # Claude narrative
    if scored:
        top_headlines = "\n".join(
            f'- [{a["sentiment"].upper()}] {a["title"]}'
            for a in sorted(scored, key=lambda x: x.get("impact","low") == "high", reverse=True)[:8]
        )
        prompt = f"""You are a senior analyst summarising today's Blackstone news for a large shareholder.

Top headlines:
{top_headlines}

Overall: {bullish} bullish, {bearish} bearish, {total - bullish - bearish} neutral articles.

Write 2-3 sentences summarising the news sentiment and most important events.
Focus on what matters for the stock price."""

        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        narrative = resp.content[0].text.strip()
    else:
        narrative = "No significant Blackstone news in the past 24 hours."

    signal = "bullish" if sentiment_balance == "bullish" else (
             "bearish" if sentiment_balance == "bearish" else "neutral")

    return {
        "total_articles":  total,
        "high_impact":     len(high_impact),
        "bullish":         bullish,
        "bearish":         bearish,
        "sentiment":       sentiment_balance,
        "signal":          signal,
        "narrative":       narrative,
        "top_items":       high_impact[:5],
    }
