"""
CNBC scraper — uses public pages + Pro login for premium content.
"""
import asyncio
from playwright.async_api import async_playwright
from config import CNBC_EMAIL, CNBC_PASSWORD

CNBC_SEARCH = "https://www.cnbc.com/search/?query=Blackstone&qsearchterm=blackstone"
CNBC_LOGIN  = "https://www.cnbc.com/site-login/"

BX_KEYWORDS = ["blackstone", "bx", "schwarzman", "jon gray", "private equity",
               "private credit", "alternative asset"]


async def _scrape_cnbc() -> list[dict]:
    articles = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # Login attempt
        try:
            await page.goto(CNBC_LOGIN, timeout=20000)
            await page.wait_for_timeout(2000)
            await page.fill('input[name="email"], input[type="email"]', CNBC_EMAIL)
            await page.fill('input[name="password"], input[type="password"]', CNBC_PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[CNBC] Login error: {e}")

        # Scrape search results
        try:
            await page.goto(CNBC_SEARCH, timeout=20000)
            await page.wait_for_timeout(2000)

            cards = await page.query_selector_all(
                ".SearchResult-searchResult, .Card-card, article"
            )
            for card in cards[:15]:
                try:
                    title_el   = await card.query_selector("h3, h2, .Card-title")
                    link_el    = await card.query_selector("a")
                    date_el    = await card.query_selector("time, .Card-time")
                    summary_el = await card.query_selector("p, .Card-description")

                    title   = await title_el.inner_text() if title_el else ""
                    url     = await link_el.get_attribute("href") if link_el else ""
                    date    = await date_el.inner_text() if date_el else ""
                    summary = await summary_el.inner_text() if summary_el else ""

                    if not title:
                        continue
                    text = (title + " " + summary).lower()
                    if not any(kw in text for kw in BX_KEYWORDS):
                        continue

                    articles.append({
                        "source":    "CNBC",
                        "title":     title.strip(),
                        "url":       url if url.startswith("http") else f"https://www.cnbc.com{url}",
                        "published": date.strip(),
                        "summary":   summary.strip()[:400],
                        "sentiment": None,
                        "impact":    None,
                    })
                except Exception:
                    pass
        except Exception as e:
            print(f"[CNBC] Scrape error: {e}")

        await browser.close()
    return articles


def fetch_cnbc_news() -> list[dict]:
    try:
        return asyncio.run(_scrape_cnbc())
    except Exception as e:
        print(f"[CNBC] Fatal error: {e}")
        return []
