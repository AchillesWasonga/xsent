from typing import Dict, Any, List, Tuple
from .x_fetcher import fetch_recent_tweets
from .xai_client import classify_sentiment

def analyze_topic(query: str, max_results: int = 25) -> Dict[str, Any]:
    tweets = fetch_recent_tweets(query, max_results=max_results)
    results: List[Tuple[int, float, str]] = []
    for t in tweets:
        label, score, why = classify_sentiment(t["text"])
        results.append((label, score, why))

    n = len(results)
    avg = sum(s for _, s, _ in results)/n if n else 0.0
    pos = sum(1 for l,_,__ in results if l == 1)
    neg = sum(1 for l,_,__ in results if l == -1)
    neu = n - pos - neg

    # simple rule for MVP
    signal = "YES" if avg > 0.15 and pos > neg else "NO" if avg < -0.15 and neg >= pos else "NEUTRAL"

    return {
        "query": query,
        "count": n,
        "avg_score": round(avg, 4),
        "breakdown": {"pos": pos, "neg": neg, "neu": neu},
        "signal": signal,
        "samples": [{"text": t["text"]} for t in tweets[:5]],
    }
