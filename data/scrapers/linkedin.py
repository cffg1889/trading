"""
LinkedIn scraper — logs in with user credentials and fetches
recent posts from Blackstone executives.
"""
import asyncio
from playwright.async_api import async_playwright
from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, LINKEDIN_PROFILES

EXECUTIVES = [
    {"name": "Stephen Schwarzman", "url": "https://www.linkedin.com/in/stephen-schwarzman/recent-activity/all/"},
    {"name": "Jon Gray",           "url": "https://www.linkedin.com/in/jon-gray-1b547913/recent-activity/all/"},
]


async def _scrape_linkedin() -> list[dict]:
    posts = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # Log in to LinkedIn
        try:
            await page.goto("https://www.linkedin.com/login", timeout=20000)
            await page.fill('#username', LINKEDIN_EMAIL)
            await page.fill('#password', LINKEDIN_PASSWORD)
            await page.click('[type=submit]')
            await page.wait_for_timeout(4000)

            # Check if login succeeded
            if "feed" not in page.url and "checkpoint" not in page.url:
                print("[LinkedIn] Login may have failed")
        except Exception as e:
            print(f"[LinkedIn] Login error: {e}")

        # Scrape each executive's recent posts
        for exec_info in EXECUTIVES:
            try:
                await page.goto(exec_info["url"], timeout=20000)
                await page.wait_for_timeout(3000)

                # Scroll to load more posts
                for _ in range(3):
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(1000)

                post_elements = await page.query_selector_all(
                    ".feed-shared-update-v2, .occludable-update, article"
                )

                for el in post_elements[:5]:
                    try:
                        text_el = await el.query_selector(
                            ".feed-shared-text, .update-components-text, "
                            "[data-test-id='main-feed-activity-card__commentary']"
                        )
                        time_el = await el.query_selector("time, span.visually-hidden")
                        link_el = await el.query_selector("a.app-aware-link")

                        content   = await text_el.inner_text() if text_el else ""
                        posted_at = await time_el.get_attribute("datetime") if time_el else ""
                        url       = await link_el.get_attribute("href") if link_el else exec_info["url"]

                        if not content or len(content) < 20:
                            continue

                        posts.append({
                            "platform":  "LinkedIn",
                            "author":    exec_info["name"],
                            "content":   content.strip()[:1000],
                            "url":       url,
                            "posted_at": posted_at,
                            "sentiment": None,
                            "relevance": None,
                        })
                    except Exception:
                        pass
            except Exception as e:
                print(f"[LinkedIn] Error scraping {exec_info['name']}: {e}")

        await browser.close()
    return posts


def fetch_linkedin_posts() -> list[dict]:
    try:
        return asyncio.run(_scrape_linkedin())
    except Exception as e:
        print(f"[LinkedIn] Fatal error: {e}")
        return []
