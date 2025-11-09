import os, requests
from typing import List, Dict
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

X_BEARER = os.getenv("X_BEARER")
if not X_BEARER:
    raise RuntimeError("X_BEARER missing in .env")

SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

def fetch_recent_tweets(query: str, max_results: int = 30) -> List[Dict]:
    """
    Returns list of tweet dicts (id, text, created_at, metrics, lang, author_id).
    Requires Elevated v2 recent search access on your app.
    """
    headers = {"Authorization": f"Bearer {X_BEARER}"}
    params = {
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,lang,public_metrics,author_id",
    }
    r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"X API error {r.status_code}: {r.text}")
    return r.json().get("data", [])
