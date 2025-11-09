# backend/x_fetcher.py
import os, time, requests

X_BEARER = os.getenv("X_BEARER", "").strip()
X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

# Simple retry/backoff for rate limits
def _req_with_retry(url, headers, params, tries=3, timeout=15):
    backoffs = [3, 8, 20]
    for i in range(tries):
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 429:
            if i < tries - 1:
                wait = backoffs[i]
                print(f"[x_fetcher] 429 Too Many Requests. Backing off {wait}s (attempt {i+1})")
                time.sleep(wait)
                continue
        r.raise_for_status()
        return r
    # last try
    r.raise_for_status()
    return r

def fetch_recent_tweets(query: str, max_results: int = 10):
    if not X_BEARER:
        # Fallback demo tweets
        print("[x_fetcher] No X_BEARER provided — using fallback demo tweets.")
        demo = [f"{query} looks strong today. Momentum building." ,
                f"Mixed feelings on {query}; waiting for clarity.",
                f"Bearish take on {query} — recent news spooked me.",
                f"I'm cautiously optimistic about {query}.",
                f"Hype around {query} is overblown, IMO."]
        return [{"id": f"demo-{i+1}", "text": t} for i, t in enumerate(demo[:max_results])]

    headers = {"Authorization": f"Bearer {X_BEARER}"}
    params = {
        "query": query,
        "max_results": max(10, min(100, max_results*2)),  # ask for a bit more; we’ll trim
        "tweet.fields": "lang,created_at",
    }
    r = _req_with_retry(X_SEARCH_URL, headers, params, tries=3, timeout=20)
    data = r.json()
    tweets = data.get("data", [])
    # keep english and trim length
    out = []
    for t in tweets:
        if t.get("lang") == "en":
            out.append({"id": t["id"], "text": t.get("text","")})
        if len(out) >= max_results:
            break
    # last resort: if empty (e.g., query too narrow), allow non-lang filter
    if not out:
        out = [{"id": t["id"], "text": t.get("text","")} for t in tweets[:max_results]]
    return out
