"""
RSS feed scraper — no API key required.
Sources: Reuters, Yahoo Finance, Google News, Seeking Alpha.
"""
import feedparser
import requests
from datetime import datetime, timezone
from urllib.parse import quote

FEEDS = [
    {
        "name": "Yahoo Finance",
        "url":  "https://finance.yahoo.com/rss/headline?s=BX",
    },
    {
        "name": "Google News – Blackstone",
        "url":  "https://news.google.com/rss/search?q=Blackstone+BX+stock&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News – Schwarzman",
        "url":  "https://news.google.com/rss/search?q=Steve+Schwarzman+Blackstone&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Seeking Alpha",
        "url":  "https://seekingalpha.com/symbol/BX/feed.xml",
    },
    {
        "name": "Reuters – Blackstone",
        "url":  "https://feeds.reuters.com/reuters/companyNews",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

BX_KEYWORDS = [
    "blackstone", "bx", "schwarzman", "jon gray", "alternative asset",
    "private equity", "private credit", "real estate fund",
]


def _is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in BX_KEYWORDS)


def fetch_rss_news() -> list[dict]:
    items = []
    for feed_cfg in FEEDS:
        try:
            feed = feedparser.parse(feed_cfg["url"])
            for entry in feed.entries[:20]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                if not _is_relevant(title, summary):
                    continue

                published = entry.get("published", "")
                try:
                    pub_dt = datetime(*entry.published_parsed[:6],
                                      tzinfo=timezone.utc).isoformat()
                except Exception:
                    pub_dt = published

                items.append({
                    "source":    feed_cfg["name"],
                    "title":     title,
                    "url":       entry.get("link", ""),
                    "published": pub_dt,
                    "summary":   summary[:500],
                    "sentiment": None,   # filled by news agent
                    "impact":    None,
                })
        except Exception as e:
            print(f"[RSS] Error fetching {feed_cfg['name']}: {e}")

    # De-duplicate by URL
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    return unique
