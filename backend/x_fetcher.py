# backend/x_fetcher.py
import os
import time
import requests
from typing import Dict, List

# Load .env here too (in case this module is imported before app.py)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

X_BEARER = os.getenv("X_BEARER", "").strip()
FORCE_DEMO = os.getenv("XSENT_FORCE_DEMO", "0") == "1"

SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

# Obvious demo set (only if FORCE_DEMO=1 or we fail all retries)
DEMO_TWEETS = [
    {"id": "demo-1", "text": "{q} looks strong today. Momentum building."},
    {"id": "demo-2", "text": "Mixed feelings on {q}; waiting for clarity."},
    {"id": "demo-3", "text": "Bearish take on {q} — recent news spooked me."},
    {"id": "demo-4", "text": "I'm cautiously optimistic about {q}."},
    {"id": "demo-5", "text": "Hype around {q} is overblown, IMO."},
]

def _auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {X_BEARER}"} if X_BEARER else {}

def _fallback(query: str, k: int) -> Dict:
    items = [{"id": t["id"], "text": t["text"].format(q=query)} for t in DEMO_TWEETS][:k]
    return {"source": "DEMO", "items": items}

def fetch_recent_tweets(query: str, max_results: int = 10, lang: str = "en") -> Dict:
    """
    Returns: {"source": "LIVE"|"DEMO", "items": [{"id","text"}]}
    We do a single-page Recent Search and cap to max_results to stay within rate limits.
    Never raises—falls back to DEMO with logs on failure.
    """
    max_results = max(1, min(int(max_results), 100))  # API page cap

    if FORCE_DEMO:
        return _fallback(query, max_results)

    if not X_BEARER:
        print("[x_fetcher] WARNING: X_BEARER missing. Using DEMO. Set X_BEARER in .env and restart.")
        return _fallback(query, max_results)

    params = {
        "query": f"({query}) lang:{lang}" if lang else query,
        "max_results": max_results,
        "tweet.fields": "lang,created_at",
    }

    tries, backoff = 0, 3
    while tries < 3:
        tries += 1
        try:
            r = requests.get(SEARCH_URL, headers=_auth_headers(), params=params, timeout=25)
            if r.status_code == 429:
                print(f"[x_fetcher] 429 Too Many Requests. Backoff {backoff}s (attempt {tries})")
                time.sleep(backoff); backoff *= 2
                continue

            if r.status_code >= 400:
                print(f"[x_fetcher] HTTP {r.status_code}: {r.text[:300]}")
                # Don’t raise—retry then fallback
                time.sleep(backoff); backoff *= 2
                continue

            data = r.json()
            raw = data.get("data", []) or []
            items = [{"id": t.get("id"), "text": t.get("text", "")} for t in raw][:max_results]
            print(f"[x_fetcher] LIVE fetched {len(items)} items for query='{query}'")
            return {"source": "LIVE", "items": items}

        except Exception as e:
            print(f"[x_fetcher] error: {type(e).__name__}: {e} (attempt {tries})")
            time.sleep(backoff); backoff *= 2

    print("[x_fetcher] Falling back to DEMO after repeated failures.")
    return _fallback(query, max_results)
