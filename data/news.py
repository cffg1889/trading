"""
News scraping from RSS feeds, WSJ, CNBC, and SEC EDGAR.
No paid APIs required.
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List
import re
import config


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    summary: str = ""
    published: str = ""
    sentiment: str = "neutral"  # bullish / bearish / neutral


# ── RSS Feeds (free, no auth) ─────────────────────────────────────────────────

RSS_FEEDS = {
    "Reuters Business":  "https://feeds.reuters.com/reuters/businessNews",
    "Yahoo Finance BX":  "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BX&region=US&lang=en-US",
    "Seeking Alpha BX":  "https://seekingalpha.com/symbol/BX.xml",
    "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "FT Markets":        "https://www.ft.com/markets?format=rss",
    "CNBC Finance":      "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "Google News BX":    "https://news.google.com/rss/search?q=Blackstone+BX+stock&hl=en-US&gl=US&ceid=US:en",
    "Google News Schwarzman": "https://news.google.com/rss/search?q=Steve+Schwarzman+Blackstone&hl=en-US&gl=US&ceid=US:en",
    "Google News PE":    "https://news.google.com/rss/search?q=private+equity+Blackstone&hl=en-US&gl=US&ceid=US:en",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

KEYWORDS = ["blackstone", "BX", "schwarzman", "jon gray", "alternative assets",
            "private equity", "private credit", "real estate pe"]

BEARISH_WORDS = ["downgrade", "cut", "miss", "decline", "fall", "drop", "concern",
                 "risk", "loss", "underperform", "sell", "bearish", "weak", "disappoints"]
BULLISH_WORDS = ["upgrade", "beat", "buy", "outperform", "strong", "growth", "raise",
                 "positive", "bullish", "record", "exceeds", "inflows", "momentum"]


def _is_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS)


def _score_sentiment(text: str) -> str:
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def fetch_rss_news(max_per_feed: int = 5, hours_back: int = 24) -> List[NewsItem]:
    """Fetch news from all RSS feeds, filter for BX relevance."""
    items = []
    cutoff = datetime.now() - timedelta(hours=hours_back)

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link = entry.get("link", "")
                published = entry.get("published", "")

                # For Yahoo Finance BX and Google News BX, all entries are relevant
                # For others, check for BX keywords
                if "BX" in url or "Blackstone" in url or _is_relevant(title + " " + summary):
                    # Clean HTML from summary
                    clean_summary = BeautifulSoup(summary, "lxml").get_text()[:300]
                    items.append(NewsItem(
                        title=title,
                        source=source,
                        url=link,
                        summary=clean_summary,
                        published=published,
                        sentiment=_score_sentiment(title + " " + clean_summary),
                    ))
        except Exception as e:
            print(f"[news] RSS error ({source}): {e}")

    return items


def fetch_edgar_filings(days_back: int = 30) -> List[NewsItem]:
    """Fetch recent SEC filings for Blackstone (CIK: 0001393818)."""
    BX_CIK = "0001393818"
    url = f"https://data.sec.gov/submissions/CIK{BX_CIK}.json"

    try:
        r = requests.get(url, headers={"User-Agent": "BX Intelligence yves@example.com"}, timeout=10)
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})

        items = []
        dates = filings.get("filingDate", [])
        forms = filings.get("form", [])
        descriptions = filings.get("primaryDocument", [])
        accessions = filings.get("accessionNumber", [])
        cutoff = datetime.now() - timedelta(days=days_back)

        for i, date_str in enumerate(dates):
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                if date < cutoff:
                    break
                form = forms[i] if i < len(forms) else ""
                acc = accessions[i].replace("-", "") if i < len(accessions) else ""
                url_filing = f"https://www.sec.gov/Archives/edgar/data/{BX_CIK.lstrip('0')}/{acc}/"

                # Only highlight important forms
                if form in ["8-K", "10-Q", "10-K", "SC 13D", "SC 13G", "4"]:
                    sentiment = "bullish" if form in ["8-K"] else "neutral"
                    items.append(NewsItem(
                        title=f"SEC Filing: {form} — {date_str}",
                        source="SEC EDGAR",
                        url=url_filing,
                        summary=f"Blackstone filed {form} with the SEC on {date_str}",
                        published=date_str,
                        sentiment=sentiment,
                    ))
            except Exception:
                continue
        return items
    except Exception as e:
        print(f"[news] EDGAR error: {e}")
        return []


def fetch_all_news(hours_back: int = 24) -> List[NewsItem]:
    """Aggregate all news sources, deduplicate, sort by recency."""
    news = fetch_rss_news(hours_back=hours_back)
    filings = fetch_edgar_filings(days_back=max(1, hours_back // 24))
    all_news = news + filings

    # Deduplicate by title similarity
    seen_titles = set()
    unique_news = []
    for item in all_news:
        title_key = re.sub(r'[^a-z0-9]', '', item.title.lower())[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_news.append(item)

    return unique_news[:30]  # top 30
