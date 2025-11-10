# backend/aggregator.py
from __future__ import annotations
from typing import Dict, List
from backend.x_fetcher import fetch_recent_tweets
from backend.xai_client import score_text

def analyze_topic(query: str, max_results: int = 20, lang: str = "en") -> Dict:
    """
    Fetch recent tweets from X and compute an average sentiment.

    Returns:
      {
        "query": str,
        "requested": int,
        "n": int,                      # number actually scored
        "avg_score": float,
        "counts": {"pos": int, "neg": int, "neu": int},
        "items": [{"id","text","score","label"}],
        "source": "LIVE"|"DEMO"
      }
    """
    max_results = max(1, min(int(max_results), 300))
    fetched = fetch_recent_tweets(query=query, max_results=max_results, lang=lang)
    source = fetched.get("source", "UNKNOWN")
    raw_items = fetched.get("items", []) or []

    out_items: List[Dict] = []
    pos = neg = neu = 0
    total = 0.0

    for t in raw_items:
        text = t.get("text", "") or ""
        sid = t.get("id")
        s = score_text(text)
        score = float(s["score"])
        label = str(s["label"])

        total += score
        if label == "pos":
            pos += 1
        elif label == "neg":
            neg += 1
        else:
            neu += 1

        out_items.append({
            "id": sid,
            "text": text,
            "score": score,
            "label": label,
        })

    n = len(out_items)
    avg = (total / n) if n else 0.0

    return {
        "query": query,
        "requested": max_results,
        "n": n,
        "avg_score": round(avg, 4),
        "counts": {"pos": pos, "neg": neg, "neu": neu},
        "items": out_items,
        "source": source,
    }
