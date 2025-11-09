# backend/aggregator.py
import time
from statistics import fmean
from backend.x_fetcher import fetch_recent_tweets
from backend.xai_client import score_with_xai

def analyze_topic(query: str, max_results: int = 10):
    """
    Fetch tweets, score each, enforce a soft deadline to avoid UI timeouts.
    """
    start = time.time()
    DEADLINE = 25.0  # seconds total budget

    tweets = fetch_recent_tweets(query, max_results=max_results)
    items, pos, neg, neu = [], 0, 0, 0

    for i, tw in enumerate(tweets[:max_results], 1):
        if time.time() - start > DEADLINE:
            break
        score = score_with_xai(tw["text"], timeout=6.0)
        label = "pos" if score > 0.15 else "neg" if score < -0.15 else "neu"
        pos += (label == "pos")
        neg += (label == "neg")
        neu += (label == "neu")
        items.append({"id": tw["id"], "text": tw["text"], "score": score, "label": label})

    avg = fmean([x["score"] for x in items]) if items else 0.0
    return {"query": query, "avg_score": avg, "counts": {"pos": pos, "neg": neg, "neu": neu}, "items": items}
