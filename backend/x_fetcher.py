# backend/x_fetcher.py
import os, time, requests
from typing import List, Dict
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

X_BEARER = os.getenv("X_BEARER")
if not X_BEARER:
    raise RuntimeError("X_BEARER missing in .env")

SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

# Set XSENT_ALLOW_FALLBACK=0 in .env to disable demo fallback
ALLOW_FALLBACK = os.getenv("XSENT_ALLOW_FALLBACK", "1") != "0"

def _fallback_tweets(query: str, n: int) -> List[Dict]:
    demo = [
        f"{query} looks strong today. Momentum building, lot of buzz.",
        f"Mixed feelings on {query}; waiting for clarity before jumping in.",
        f"Bearish take on {query}—recent news spooked me.",
        f"I'm cautiously optimistic about {query}.",
        f"Hype around {query} is overblown, IMO.",
        f"Solid fundamentals for {query} if the macro holds.",
        f"Short term noise; long term bullish on {query}.",
        f"{query} is getting too volatile for me right now.",
        f"Sentiment on {query} feels like a turning point.",
        f"Leaning negative on {query} until we see better data.",
    ]
    demo = demo[:max(1, min(n, len(demo)))]
    return [{"id": f"demo-{i}", "text": t} for i, t in enumerate(demo, 1)]

def fetch_recent_tweets(query: str, max_results: int = 30) -> List[Dict]:
    """
    Returns list of tweet dicts (id, text, created_at, metrics, lang, author_id).
    Handles 429 with exponential backoff; optional demo fallback if rate-limited.
    """
    headers = {"Authorization": f"Bearer {X_BEARER}"}
    params = {
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,lang,public_metrics,author_id",
    }

    backoffs = [3, 8, 20]  # seconds
    for attempt in range(len(backoffs) + 1):
        r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=20)

        # Success
        if r.status_code == 200:
            return r.json().get("data", [])

        # Rate limit -> backoff
        if r.status_code == 429 and attempt < len(backoffs):
            wait = backoffs[attempt]
            print(f"[x_fetcher] 429 Too Many Requests. Backing off {wait}s (attempt {attempt+1})")
            time.sleep(wait)
            continue

        # Other auth issues -> graceful message or fallback
        if r.status_code in (401, 403):
            msg = (
                f"X API auth error {r.status_code}. "
                "Check Bearer token and app access level (v2 Recent Search requires Elevated)."
            )
            if ALLOW_FALLBACK:
                print(f"[x_fetcher] {msg} Using demo fallback tweets.")
                return _fallback_tweets(query, min(max_results, 10))
            raise RuntimeError(f"{msg} Body: {r.text}")

        # Final 429 after retries -> fallback or raise
        if r.status_code == 429 and attempt == len(backoffs):
            if ALLOW_FALLBACK:
                print("[x_fetcher] Exhausted retries on 429. Using demo fallback tweets.")
                return _fallback_tweets(query, min(max_results, 10))
            raise RuntimeError(f"X API error 429 after retries: {r.text}")

        # Other errors
        raise RuntimeError(f"X API error {r.status_code}: {r.text}")
