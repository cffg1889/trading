"""
Social Media Agent — scrapes LinkedIn executive posts and public
Twitter/X commentary, analyses with Claude.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from data.scrapers.linkedin import fetch_linkedin_posts
from data import store

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _score_posts(posts: list[dict]) -> list[dict]:
    if not posts:
        return []

    posts_text = "\n".join(
        f'{i+1}. [{p["platform"]}] {p["author"]}: {p["content"][:200]}'
        for i, p in enumerate(posts[:10])
    )

    prompt = f"""You are an analyst reviewing social media posts from Blackstone executives
and commentators. Score each post for market relevance and sentiment.

{posts_text}

Respond ONLY with valid JSON array (same order):
[{{"sentiment": "bullish|bearish|neutral",
   "relevance": "high|medium|low",
   "key_insight": "one sentence insight for investor"}}]"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        text   = response.content[0].text
        start  = text.find("[")
        end    = text.rfind("]") + 1
        scores = json.loads(text[start:end])
        for i, score in enumerate(scores[:len(posts)]):
            posts[i]["sentiment"]  = score.get("sentiment", "neutral")
            posts[i]["relevance"]  = score.get("relevance", "low")
            posts[i]["key_insight"]= score.get("key_insight", "")
    except Exception as e:
        print(f"[Social] Scoring error: {e}")

    return posts


def run() -> dict:
    """Fetch and analyse executive social posts."""
    posts = []

    try:
        linkedin = fetch_linkedin_posts()
        posts.extend(linkedin)
    except Exception as e:
        print(f"[Social] LinkedIn error: {e}")

    if not posts:
        return {
            "signal":    "neutral",
            "narrative": "No recent executive social media activity detected.",
            "posts":     [],
        }

    scored = _score_posts(posts)
    store.save_social_posts(scored)

    high_relevance = [p for p in scored if p.get("relevance") == "high"]
    bullish = sum(1 for p in scored if p.get("sentiment") == "bullish")
    bearish = sum(1 for p in scored if p.get("sentiment") == "bearish")

    # Claude narrative
    if high_relevance:
        insights = "\n".join(
            f'- {p["author"]}: {p.get("key_insight", p["content"][:100])}'
            for p in high_relevance[:5]
        )
        prompt = f"""Summarise these Blackstone executive social media signals in 2 sentences
for a large shareholder making investment decisions:
{insights}"""
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        narrative = resp.content[0].text.strip()
    else:
        narrative = "No high-relevance executive posts detected recently."

    signal = "bullish" if bullish > bearish else ("bearish" if bearish > bullish else "neutral")

    return {
        "signal":         signal,
        "total_posts":    len(scored),
        "high_relevance": len(high_relevance),
        "bullish":        bullish,
        "bearish":        bearish,
        "narrative":      narrative,
        "posts":          high_relevance[:3],
    }
