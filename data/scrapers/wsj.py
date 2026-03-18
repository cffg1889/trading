"""
WSJ scraper using Playwright with subscriber credentials.
Searches for Blackstone news and returns articles.
"""
import asyncio
from playwright.async_api import async_playwright
from config import WSJ_EMAIL, WSJ_PASSWORD

WSJ_SEARCH = "https://www.wsj.com/search?query=Blackstone&mod=searchresults_viewallresults"
WSJ_LOGIN  = "https://accounts.wsj.com/login"

BX_KEYWORDS = ["blackstone", "bx", "schwarzman", "jon gray", "private equity"]


async def _scrape_wsj() -> list[dict]:
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

        # Log in
        try:
            await page.goto(WSJ_LOGIN, timeout=20000)
            await page.fill('input[name="username"]', WSJ_EMAIL)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(1500)
            await page.fill('input[name="password"]', WSJ_PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[WSJ] Login error: {e}")

        # Search
        try:
            await page.goto(WSJ_SEARCH, timeout=20000)
            await page.wait_for_timeout(2000)

            items = await page.query_selector_all("article, .WSJTheme--story--XB4V2mLz")
            for item in items[:15]:
                try:
                    title_el   = await item.query_selector("h3, h2, .WSJTheme--headline--unZqjb45")
                    link_el    = await item.query_selector("a")
                    date_el    = await item.query_selector("time, p.WSJTheme--timestamp")
                    summary_el = await item.query_selector("p.WSJTheme--summary")

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
                        "source":    "WSJ",
                        "title":     title.strip(),
                        "url":       url if url.startswith("http") else f"https://www.wsj.com{url}",
                        "published": date.strip(),
                        "summary":   summary.strip()[:400],
                        "sentiment": None,
                        "impact":    None,
                    })
                except Exception:
                    pass
        except Exception as e:
            print(f"[WSJ] Scrape error: {e}")

        await browser.close()
    return articles


def fetch_wsj_news() -> list[dict]:
    try:
        return asyncio.run(_scrape_wsj())
    except Exception as e:
        print(f"[WSJ] Fatal error: {e}")
        return []
