"""
Analyst Tracker Agent — monitors rating changes, price target revisions,
and consensus movements for BX.
"""
import json
import requests
from bs4 import BeautifulSoup
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, TICKER
from data import store

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_benzinga_ratings() -> list[dict]:
    """Scrape recent analyst ratings from Benzinga public page."""
    url = f"https://www.benzinga.com/quote/{TICKER}/analyst-ratings"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        ratings = []
        rows    = soup.select("table tbody tr")
        for row in rows[:15]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 5:
                ratings.append({
                    "date":       cols[0],
                    "firm":       cols[1],
                    "action":     cols[2],
                    "old_rating": cols[3],
                    "new_rating": cols[4],
                    "old_target": None,
                    "new_target": cols[5] if len(cols) > 5 else None,
                })
        return ratings
    except Exception as e:
        print(f"[Analyst] Benzinga error: {e}")
        return []


def _fetch_finviz_ratings() -> list[dict]:
    """Scrape analyst ratings from Finviz."""
    url = f"https://finviz.com/quote.ashx?t={TICKER}"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")

        ratings = []
        table   = soup.find("table", class_="fullview-ratings-outer")
        if not table:
            return []

        rows = table.find_all("tr")
        for row in rows[1:16]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 4:
                ratings.append({
                    "date":       cols[0],
                    "firm":       cols[1],
                    "action":     cols[2],
                    "old_rating": None,
                    "new_rating": cols[3],
                    "old_target": None,
                    "new_target": cols[4] if len(cols) > 4 else None,
                })
        return ratings
    except Exception as e:
        print(f"[Analyst] Finviz error: {e}")
        return []


def run() -> dict:
    """Fetch analyst ratings and generate summary with Claude."""
    ratings = _fetch_benzinga_ratings() or _fetch_finviz_ratings()

    # Save new ratings to DB
    for r in ratings:
        store.save_analyst_rating(r)

    # Get recent history from DB
    recent = store.get_recent_analyst_ratings(days=30)

    if not recent:
        return {
            "signal":    "neutral",
            "narrative": "No recent analyst rating changes for BX.",
            "upgrades":  0,
            "downgrades": 0,
        }

    upgrades   = sum(1 for r in recent if "upgrade" in (r.get("action") or "").lower())
    downgrades = sum(1 for r in recent if "downgrade" in (r.get("action") or "").lower())
    pt_changes = [r for r in recent if r.get("new_target")]

    ratings_text = "\n".join(
        f"- {r.get('date','')} {r.get('firm','')} {r.get('action','')} "
        f"{r.get('old_rating','?')} → {r.get('new_rating','?')} "
        f"PT: {r.get('new_target','N/A')}"
        for r in recent[:10]
    )

    prompt = f"""You are a senior equity research analyst summarising recent analyst activity on Blackstone (BX).

Recent analyst actions (last 30 days):
{ratings_text}

Summary: {upgrades} upgrades, {downgrades} downgrades in the period.

Respond ONLY with valid JSON:
{{
  "signal": "bullish|neutral|bearish",
  "momentum": "improving|stable|deteriorating",
  "upgrades": {upgrades},
  "downgrades": {downgrades},
  "consensus_trend": "rising|flat|declining",
  "narrative": "2-3 sentence assessment of analyst sentiment momentum"
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response.content[0].text)
    except Exception:
        text   = response.content[0].text
        start  = text.find("{")
        end    = text.rfind("}") + 1
        result = json.loads(text[start:end])

    result["recent_ratings"] = recent[:5]
    return result
