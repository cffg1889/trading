"""
BX Intelligence — Comprehensive news and filing scraper.
Sources: SEC EDGAR (BX + BCRED + BREIT), BX IR, CNBC, WSJ, LinkedIn (management),
         Google News RSS, Yahoo Finance RSS, insider trades (Form 4).
Results cached in SQLite (db/bx.db) and refreshed every 15 min in background.
"""
import asyncio
import re
import sqlite3
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import feedparser
import requests
from bs4 import BeautifulSoup
import config

# ── Data model ────────────────────────────────────────────────────────────────

SOURCE_ICONS = {
    "SEC EDGAR":    "📄",
    "SEC Form 4":   "👤",
    "BX IR":        "🏢",
    "CNBC":         "📺",
    "WSJ":          "📰",
    "LinkedIn":     "💼",
    "Yahoo Finance":"📊",
    "Google News":  "🌐",
    "Reuters":      "🌐",
    "Seeking Alpha":"📈",
    "Other":        "🌐",
}

@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    summary: str = ""
    published: str = ""
    sentiment: str = "neutral"   # bullish / bearish / neutral
    impact: int = 1              # 1–5 (5 = most important)
    source_type: str = "news"    # sec / insider / ir / cnbc / wsj / linkedin / rss

    @property
    def icon(self) -> str:
        return SOURCE_ICONS.get(self.source, "🌐")

    @property
    def time_ago(self) -> str:
        try:
            from dateutil import parser as dp
            dt = dp.parse(self.published)
            dt = dt.replace(tzinfo=None)
            delta = datetime.now() - dt
            if delta.seconds < 3600:
                return f"{delta.seconds // 60}m ago"
            if delta.days == 0:
                return f"{delta.seconds // 3600}h ago"
            return f"{delta.days}d ago"
        except Exception:
            return self.published[:10] if self.published else ""


# ── Helpers ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

BEARISH_WORDS = ["downgrade", "cut", "miss", "decline", "fall", "drop", "concern",
                 "risk", "loss", "underperform", "sell", "bearish", "weak",
                 "disappoints", "redemption", "outflows", "warning", "lawsuit"]
BULLISH_WORDS = ["upgrade", "beat", "buy", "outperform", "strong", "growth", "raise",
                 "positive", "bullish", "record", "exceeds", "inflows", "momentum",
                 "acquisition", "deal", "partnership", "raises", "fund"]
BX_KEYWORDS   = ["blackstone", " bx ", "bx stock", "schwarzman", "jon gray",
                 "breit", "bcred", "alternative assets", "private equity blackstone"]

HIGH_IMPACT_WORDS = ["earnings", "8-k", "10-q", "acquisition", "merger", "dividend",
                     "upgrade", "downgrade", "insider", "bought", "sold", "form 4",
                     "quarterly", "annual", "ceo", "president", "billion", "fund raise"]


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in BX_KEYWORDS)


def _score_sentiment(text: str) -> str:
    t = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in t)
    bear = sum(1 for w in BEARISH_WORDS if w in t)
    return "bullish" if bull > bear else "bearish" if bear > bull else "neutral"


def _score_impact(title: str, source: str, source_type: str) -> int:
    """Rate importance 1-5. SEC filings and insider trades start higher."""
    score = 1
    t = (title + " " + source).lower()
    # Source type bonus
    if source_type in ("sec", "insider"):
        score += 3
    elif source_type in ("ir", "linkedin"):
        score += 2
    elif source_type in ("cnbc", "wsj"):
        score += 2
    # Keyword bonus
    if any(w in t for w in HIGH_IMPACT_WORDS):
        score += 1
    return min(score, 5)


def _clean(html: str, max_len: int = 400) -> str:
    text = BeautifulSoup(html or "", "lxml").get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


# ── SQLite cache ──────────────────────────────────────────────────────────────

_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "db", "bx.db"))


def _get_conn():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_cache (
            id          TEXT PRIMARY KEY,
            title       TEXT,
            source      TEXT,
            url         TEXT,
            summary     TEXT,
            published   TEXT,
            sentiment   TEXT,
            impact      INTEGER,
            source_type TEXT,
            fetched_at  TEXT
        )
    """)
    conn.commit()
    return conn


def _save_items(items: List[NewsItem]):
    conn = _get_conn()
    now = datetime.now().isoformat()
    for it in items:
        uid = re.sub(r"[^a-z0-9]", "", it.title.lower())[:60]
        conn.execute("""
            INSERT OR REPLACE INTO news_cache
            (id, title, source, url, summary, published, sentiment, impact, source_type, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (uid, it.title, it.source, it.url, it.summary,
              it.published, it.sentiment, it.impact, it.source_type, now))
    conn.commit()
    conn.close()


def _load_cached(hours_back: int = 48) -> List[NewsItem]:
    try:
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(hours=hours_back)).isoformat()
        rows = conn.execute(
            "SELECT title,source,url,summary,published,sentiment,impact,source_type "
            "FROM news_cache WHERE fetched_at > ? ORDER BY impact DESC, fetched_at DESC LIMIT 80",
            (cutoff,)
        ).fetchall()
        conn.close()
        return [NewsItem(title=r[0], source=r[1], url=r[2], summary=r[3],
                         published=r[4], sentiment=r[5], impact=r[6], source_type=r[7])
                for r in rows]
    except Exception:
        return []


# ── Source 1: RSS feeds ───────────────────────────────────────────────────────

RSS_FEEDS = {
    "Yahoo Finance":   "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BX&region=US&lang=en-US",
    "Google News BX":  "https://news.google.com/rss/search?q=Blackstone+BX+NYSE&hl=en-US&gl=US&ceid=US:en",
    "Google News Mgmt":"https://news.google.com/rss/search?q=Jon+Gray+OR+Schwarzman+Blackstone&hl=en-US&gl=US&ceid=US:en",
    "Google News BREIT":"https://news.google.com/rss/search?q=BREIT+Blackstone+real+estate&hl=en-US&gl=US&ceid=US:en",
    "Google News PE":  "https://news.google.com/rss/search?q=Blackstone+private+equity+fund&hl=en-US&gl=US&ceid=US:en",
    "Seeking Alpha BX":"https://seekingalpha.com/symbol/BX.xml",
    "Reuters":         "https://feeds.reuters.com/reuters/businessNews",
    "CNBC Finance":    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
}


def fetch_rss_news(hours_back: int = 48) -> List[NewsItem]:
    items = []
    cutoff = datetime.now() - timedelta(hours=hours_back)
    for source, url in RSS_FEEDS.items():
        try:
            # Use requests to bypass macOS Python SSL cert issues with feedparser
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                feed = feedparser.parse(resp.content)
            except Exception:
                feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title   = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                link    = entry.get("link", "")
                pub     = entry.get("published", "")
                text    = title + " " + summary
                if not _is_relevant(text) and "BX" not in url and "Blackstone" not in url:
                    continue
                clean = _clean(summary)
                stype = "cnbc" if "cnbc" in source.lower() else "rss"
                imp   = _score_impact(title, source, stype)
                items.append(NewsItem(
                    title=title, source=source, url=link, summary=clean,
                    published=pub, sentiment=_score_sentiment(text),
                    impact=imp, source_type=stype,
                ))
        except Exception as e:
            print(f"[rss] {source}: {e}")
    return items


# ── Source 2: SEC EDGAR (BX + BCRED + BREIT) ─────────────────────────────────

EDGAR_ENTITIES = {
    "Blackstone Inc (BX)":   "0001393818",
    "BCRED":                  "0001655888",
    "BREIT":                  "0001646587",
}
EDGAR_HEADERS = {"User-Agent": "BX Intelligence research@bxintel.com"}
KEY_FORMS = {"8-K", "10-Q", "10-K", "SC 13D", "SC 13G", "DEF 14A", "S-11", "N-2"}


def fetch_edgar_filings(days_back: int = 60) -> List[NewsItem]:
    items = []
    cutoff = datetime.now() - timedelta(days=days_back)
    for entity, cik in EDGAR_ENTITIES.items():
        try:
            r = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=EDGAR_HEADERS, timeout=10
            )
            data = r.json()
            f = data.get("filings", {}).get("recent", {})
            dates    = f.get("filingDate", [])
            forms    = f.get("form", [])
            accessions = f.get("accessionNumber", [])
            descriptions = f.get("primaryDocument", [])

            for i, d in enumerate(dates):
                try:
                    if datetime.strptime(d, "%Y-%m-%d") < cutoff:
                        break
                    form = forms[i] if i < len(forms) else ""
                    if form not in KEY_FORMS:
                        continue
                    acc = accessions[i].replace("-", "") if i < len(accessions) else ""
                    cik_clean = cik.lstrip("0")
                    url_f = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc}/"
                    desc = descriptions[i] if i < len(descriptions) else ""
                    title = f"SEC {form} — {entity} ({d})"
                    summary = f"{entity} filed {form} with the SEC on {d}. Document: {desc}"
                    items.append(NewsItem(
                        title=title, source="SEC EDGAR", url=url_f,
                        summary=summary, published=d,
                        sentiment="neutral", impact=_score_impact(title, "SEC EDGAR", "sec"),
                        source_type="sec",
                    ))
                except Exception:
                    continue
        except Exception as e:
            print(f"[edgar] {entity}: {e}")
    return items


def fetch_insider_trades(days_back: int = 60) -> List[NewsItem]:
    """
    Fetch BX insider trades from SEC Form 4.
    Parses the actual Form 4 XML to extract: insider name, role, shares, price.
    Returns clean one-line items like "Jonathan Gray (President) bought 10,000 shares @ $113.42".
    """
    items = []
    try:
        # Get the list of Form 4 filings for BX (as issuer) from EDGAR company search
        list_url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            "?action=getcompany&CIK=0001393818&type=4"
            "&dateb=&owner=include&count=15&search_text="
        )
        r = requests.get(list_url, headers=EDGAR_HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "lxml")
        cutoff = datetime.now() - timedelta(days=days_back)

        table = soup.find("table", class_="tableFile2")
        if not table:
            return items

        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            if cols[0].get_text(strip=True) not in ("4", "4/A"):
                continue
            date_text = cols[3].get_text(strip=True)
            try:
                if datetime.strptime(date_text, "%Y-%m-%d") < cutoff:
                    continue
            except Exception:
                pass

            # Link to filing index page
            link_el = cols[1].find("a")
            if not link_el:
                continue
            index_href = link_el.get("href", "")
            if not index_href.startswith("http"):
                index_href = "https://www.sec.gov" + index_href

            try:
                # ── Step 1: get filing index → find Form 4 XML ────────────────
                idx_r = requests.get(index_href, headers=EDGAR_HEADERS, timeout=8)
                idx_soup = BeautifulSoup(idx_r.text, "lxml")
                xml_url = None
                # Prefer ownership.xml (the actual Form 4 data, not the xsl-styled version)
                for a in idx_soup.find_all("a", href=True):
                    href = a["href"]
                    if "xsl" in href:
                        continue  # skip the XSL-styled version
                    if href.endswith(".xml") and "index" not in href:
                        xml_url = ("https://www.sec.gov" + href
                                   if not href.startswith("http") else href)
                        break
                if not xml_url:
                    continue

                # ── Step 2: parse Form 4 XML with BeautifulSoup (handles malformed XML) ──
                xml_r = requests.get(xml_url, headers=EDGAR_HEADERS, timeout=8)
                doc = BeautifulSoup(xml_r.content, "xml")

                # ── Step 3: verify BX is the ISSUER (not just reporting owner) ──
                issuer_cik_el = doc.find("issuerCik")
                if not issuer_cik_el:
                    continue
                issuer_cik = (issuer_cik_el.get_text() or "").strip().lstrip("0")
                if issuer_cik != "1393818":
                    continue  # BX filing as investor in another company, skip

                # Insider identity
                owner_name = (doc.find("rptOwnerName") or {}).get_text("").strip()
                officer_el = doc.find("officerTitle")
                officer_title = officer_el.get_text("").strip() if officer_el else ""
                dir_el = doc.find("isDirector")
                is_director = (dir_el.get_text("").strip() == "1") if dir_el else False

                if not owner_name:
                    continue

                # Transactions (non-derivative = actual BX shares)
                acquired, disposed = 0.0, 0.0
                buy_price, sell_price = None, None

                def _txt(parent, tag):
                    el = parent.find(tag)
                    return el.get_text("").strip() if el else ""

                for txn in doc.find_all("nonDerivativeTransaction"):
                    try:
                        shares_str = _txt(txn, "transactionShares")
                        # transactionShares contains a nested <value>
                        shares_val = txn.find("transactionShares")
                        val_el = shares_val.find("value") if shares_val else None
                        shares = float(val_el.get_text().strip()) if val_el else 0.0

                        price_el = txn.find("transactionPricePerShare")
                        price_val = price_el.find("value") if price_el else None
                        price = float(price_val.get_text().strip()) if price_val else None

                        code_el = txn.find("transactionAcquiredDisposedCode")
                        code_val = code_el.find("value") if code_el else None
                        code = code_val.get_text().strip() if code_val else ""

                        if code == "A":
                            acquired += shares
                            if price:
                                buy_price = price
                        elif code == "D":
                            disposed += shares
                            if price:
                                sell_price = price
                    except Exception:
                        continue

                # ── Step 3: format human-readable title ───────────────────────
                # EDGAR stores names as "LASTNAME FIRSTNAME" (all caps) or mixed case
                parts = owner_name.split()
                if owner_name == owner_name.upper() and len(parts) >= 2:
                    name = f"{parts[1].title()} {parts[0].title()}"
                else:
                    name = owner_name  # already readable

                role = officer_title or ("Director" if is_director else "Insider")

                if acquired > 0 and disposed == 0:
                    p = f" @ ${buy_price:,.2f}" if buy_price else ""
                    title = f"{name} ({role}) bought {int(acquired):,} shares{p}"
                    sentiment = "bullish"
                elif disposed > 0 and acquired == 0:
                    p = f" @ ${sell_price:,.2f}" if sell_price else ""
                    title = f"{name} ({role}) sold {int(disposed):,} shares{p}"
                    sentiment = "bearish"
                elif acquired > 0 and disposed > 0:
                    title = f"{name} ({role}): bought {int(acquired):,} / sold {int(disposed):,} shares"
                    sentiment = "neutral"
                else:
                    continue  # derivative-only filing, skip

                items.append(NewsItem(
                    title=title, source="SEC Form 4", url=index_href,
                    summary="",
                    published=date_text, sentiment=sentiment,
                    impact=4, source_type="insider",
                ))

            except Exception as e:
                print(f"[form4] parse error {index_href}: {e}")
                continue

    except Exception as e:
        print(f"[form4] {e}")
    return items


# ── Source 3: BX Investor Relations ──────────────────────────────────────────

def fetch_bx_ir() -> List[NewsItem]:
    """Scrape ir.blackstone.com for press releases and announcements."""
    items = []
    urls = [
        "https://ir.blackstone.com/news-releases/default.aspx",
        "https://ir.blackstone.com/investor-day/default.aspx",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            soup = BeautifulSoup(r.text, "lxml")
            # Find news release links
            for a in soup.find_all("a", href=True)[:20]:
                href = a["href"]
                text = a.get_text(strip=True)
                if len(text) < 15:
                    continue
                if any(kw in text.lower() for kw in ["blackstone", "earnings", "quarter", "annual",
                                                       "dividend", "fund", "billion", "acqui"]):
                    full_url = href if href.startswith("http") else "https://ir.blackstone.com" + href
                    items.append(NewsItem(
                        title=text, source="BX IR", url=full_url,
                        summary=f"Blackstone Investor Relations announcement: {text}",
                        published=datetime.now().strftime("%Y-%m-%d"),
                        sentiment=_score_sentiment(text),
                        impact=_score_impact(text, "BX IR", "ir"),
                        source_type="ir",
                    ))
        except Exception as e:
            print(f"[bx_ir] {e}")
    return items


# ── Source 4: CNBC (Playwright + login) ──────────────────────────────────────

async def _cnbc_async() -> List[NewsItem]:
    from playwright.async_api import async_playwright
    items = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()

            # Login
            await page.goto("https://www.cnbc.com/login/", timeout=20000)
            await page.wait_for_timeout(2000)
            try:
                await page.fill("input[name='email'], input[type='email']", config.CNBC_EMAIL or "")
                await page.fill("input[name='password'], input[type='password']", config.CNBC_PASSWORD or "")
                await page.click("button[type='submit']")
                await page.wait_for_timeout(3000)
            except Exception:
                pass  # login may fail, still get public articles

            # BX news page
            await page.goto("https://www.cnbc.com/quotes/BX?tab=news", timeout=20000)
            await page.wait_for_timeout(3000)

            articles = await page.query_selector_all("div.Card-standardBreakerCard, div.LatestNews-item, a.Card-title")
            for art in articles[:15]:
                try:
                    title_el = await art.query_selector("a, .Card-title")
                    title = await (title_el or art).inner_text()
                    title = title.strip()
                    if len(title) < 10:
                        continue
                    href = ""
                    try:
                        link_el = await art.query_selector("a")
                        href = await link_el.get_attribute("href") or ""
                        if href and not href.startswith("http"):
                            href = "https://www.cnbc.com" + href
                    except Exception:
                        pass
                    items.append(NewsItem(
                        title=title, source="CNBC", url=href,
                        summary=title,
                        published=datetime.now().strftime("%Y-%m-%d %H:%M"),
                        sentiment=_score_sentiment(title),
                        impact=_score_impact(title, "CNBC", "cnbc"),
                        source_type="cnbc",
                    ))
                except Exception:
                    continue

            # Also search for Blackstone
            await page.goto("https://www.cnbc.com/search/?query=blackstone&qsearchterm=blackstone", timeout=20000)
            await page.wait_for_timeout(2000)
            search_items = await page.query_selector_all(".SearchResult-searchResultContent")
            for it in search_items[:8]:
                try:
                    title_el = await it.query_selector("a.resultlink")
                    title = (await title_el.inner_text()).strip() if title_el else ""
                    if len(title) < 10 or not _is_relevant(title):
                        continue
                    href = await title_el.get_attribute("href") if title_el else ""
                    items.append(NewsItem(
                        title=title, source="CNBC", url=href or "",
                        summary=title,
                        published=datetime.now().strftime("%Y-%m-%d %H:%M"),
                        sentiment=_score_sentiment(title),
                        impact=_score_impact(title, "CNBC", "cnbc"),
                        source_type="cnbc",
                    ))
                except Exception:
                    continue

            await browser.close()
    except Exception as e:
        print(f"[cnbc] {e}")
    return items


def fetch_cnbc() -> List[NewsItem]:
    try:
        return asyncio.run(_cnbc_async())
    except Exception as e:
        print(f"[cnbc] runner error: {e}")
        return []


# ── Source 5: WSJ (Playwright + login) ───────────────────────────────────────

async def _wsj_async() -> List[NewsItem]:
    from playwright.async_api import async_playwright
    items = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()

            # Login to WSJ
            await page.goto("https://session.wsj.com/sso/login", timeout=20000)
            await page.wait_for_timeout(2000)
            try:
                await page.fill("input#username", config.WSJ_EMAIL or "")
                await page.click("button[type='submit'], .basic-login-submit")
                await page.wait_for_timeout(1500)
                await page.fill("input#password", config.WSJ_PASSWORD or "")
                await page.click("button[type='submit'], .basic-login-submit")
                await page.wait_for_timeout(3000)
            except Exception as ex:
                print(f"[wsj] login step: {ex}")

            # BX quote news page
            await page.goto("https://www.wsj.com/market-data/quotes/BX/research-ratings", timeout=20000)
            await page.wait_for_timeout(3000)

            # Search for Blackstone
            await page.goto(
                "https://www.wsj.com/search?query=blackstone&isToggleOn=true&operator=AND"
                "&sort=date-desc&duration=1y&startDate=&endDate=&source=wsj,marketwatch",
                timeout=20000
            )
            await page.wait_for_timeout(3000)

            articles = await page.query_selector_all("article, .WSJTheme--story-headline--3KBBr1b1")
            for art in articles[:12]:
                try:
                    h = await art.query_selector("h3, h2, .headline")
                    if not h:
                        continue
                    title = (await h.inner_text()).strip()
                    if len(title) < 10 or not _is_relevant(title):
                        continue
                    a_el = await art.query_selector("a")
                    href = (await a_el.get_attribute("href")) if a_el else ""
                    if href and not href.startswith("http"):
                        href = "https://www.wsj.com" + href
                    # Try to get date
                    time_el = await art.query_selector("time")
                    pub = (await time_el.get_attribute("datetime") or
                           await time_el.inner_text()) if time_el else datetime.now().strftime("%Y-%m-%d")
                    items.append(NewsItem(
                        title=title, source="WSJ", url=href or "",
                        summary=title,
                        published=str(pub),
                        sentiment=_score_sentiment(title),
                        impact=_score_impact(title, "WSJ", "wsj"),
                        source_type="wsj",
                    ))
                except Exception:
                    continue

            await browser.close()
    except Exception as e:
        print(f"[wsj] {e}")
    return items


def fetch_wsj() -> List[NewsItem]:
    try:
        return asyncio.run(_wsj_async())
    except Exception as e:
        print(f"[wsj] runner error: {e}")
        return []


# ── Source 6: LinkedIn — Management posts ────────────────────────────────────

LINKEDIN_PROFILES = {
    "Jon Gray (BX President)":      "https://www.linkedin.com/in/jon-gray-blackstone/",
    "Steve Schwarzman (BX CEO)":    "https://www.linkedin.com/in/stephenschwarzmanbx/",
    "Michael Chae (BX CFO)":        "https://www.linkedin.com/in/michael-chae-27ab131b/",
}


async def _linkedin_async() -> List[NewsItem]:
    from playwright.async_api import async_playwright
    items = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()

            # Login to LinkedIn
            await page.goto("https://www.linkedin.com/login", timeout=20000)
            await page.wait_for_timeout(2000)
            try:
                await page.fill("input#username", config.LINKEDIN_EMAIL or "")
                await page.fill("input#password", config.LINKEDIN_PASSWORD or "")
                await page.click("button[type='submit']")
                await page.wait_for_timeout(4000)
            except Exception as ex:
                print(f"[linkedin] login: {ex}")

            # Visit each executive's recent activity
            for name, profile_url in LINKEDIN_PROFILES.items():
                try:
                    activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
                    await page.goto(activity_url, timeout=20000)
                    await page.wait_for_timeout(3000)

                    posts = await page.query_selector_all(
                        ".occludable-update, .feed-shared-update-v2"
                    )
                    for post in posts[:3]:
                        try:
                            text_el = await post.query_selector(
                                ".break-words, .feed-shared-text"
                            )
                            if not text_el:
                                continue
                            text = (await text_el.inner_text()).strip()
                            if len(text) < 20:
                                continue
                            # Get post URL
                            link_el = await post.query_selector("a[href*='/posts/'], a[href*='/feed/']")
                            href = (await link_el.get_attribute("href")) if link_el else profile_url
                            title = f"{name}: {text[:100]}..."
                            items.append(NewsItem(
                                title=title, source="LinkedIn", url=href or profile_url,
                                summary=text[:400],
                                published=datetime.now().strftime("%Y-%m-%d"),
                                sentiment=_score_sentiment(text),
                                impact=4,
                                source_type="linkedin",
                            ))
                        except Exception:
                            continue
                except Exception as ex:
                    print(f"[linkedin] {name}: {ex}")

            await browser.close()
    except Exception as e:
        print(f"[linkedin] {e}")
    return items


def fetch_linkedin() -> List[NewsItem]:
    try:
        return asyncio.run(_linkedin_async())
    except Exception as e:
        print(f"[linkedin] runner error: {e}")
        return []


# ── Aggregator ────────────────────────────────────────────────────────────────

_last_refresh: Optional[datetime] = None
_cache_lock = threading.Lock()
REFRESH_INTERVAL_MIN = 15


def fetch_all_news(hours_back: int = 48, force: bool = False) -> List[NewsItem]:
    """
    Return all news items. Uses SQLite cache, refreshes every 15 min.
    On first call (cold start) fetches everything synchronously.
    """
    global _last_refresh

    with _cache_lock:
        now = datetime.now()
        needs_refresh = (
            force or
            _last_refresh is None or
            (now - _last_refresh).total_seconds() > REFRESH_INTERVAL_MIN * 60
        )

        if needs_refresh:
            _last_refresh = now
            # Run fast sources synchronously, slow (Playwright) in background
            items = []
            with ThreadPoolExecutor(max_workers=4) as ex:
                futures = {
                    ex.submit(fetch_rss_news, hours_back): "rss",
                    ex.submit(fetch_edgar_filings, max(days_back := hours_back // 24, 7)): "edgar",
                    ex.submit(fetch_insider_trades, max(days_back, 30)): "form4",
                    ex.submit(fetch_bx_ir): "ir",
                }
                for f in as_completed(futures):
                    try:
                        items.extend(f.result())
                    except Exception as e:
                        print(f"[news] source error: {e}")

            # Playwright sources in background thread to avoid blocking dashboard
            def _playwright_refresh():
                pl_items = []
                for fn in [fetch_cnbc, fetch_wsj, fetch_linkedin]:
                    try:
                        pl_items.extend(fn())
                    except Exception as e:
                        print(f"[news] playwright: {e}")
                if pl_items:
                    _save_items(pl_items)

            t = threading.Thread(target=_playwright_refresh, daemon=True)
            t.start()

            if items:
                _save_items(items)

    # Always return from cache (fast)
    cached = _load_cached(hours_back)
    if not cached:
        # Cold start fallback — return RSS immediately
        return sorted(fetch_rss_news(hours_back) + fetch_edgar_filings(30),
                      key=lambda x: x.impact, reverse=True)[:30]

    # Deduplicate
    seen, unique = set(), []
    for it in sorted(cached, key=lambda x: x.impact, reverse=True):
        key = re.sub(r"[^a-z0-9]", "", it.title.lower())[:50]
        if key not in seen:
            seen.add(key)
            unique.append(it)

    return unique[:50]
