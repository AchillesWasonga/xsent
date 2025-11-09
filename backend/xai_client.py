# backend/xai_client.py
import os, requests

XAI_KEY = os.getenv("XAI_KEY", "").strip()
# Replace with your actual xAI endpoint if available.
# Here we use a simple local heuristic fallback when no key is set.

def score_with_xai(text: str, timeout: float = 8.0) -> float:
    """
    Returns a sentiment score in [-1.0, 1.0].
    If XAI_KEY is not set, uses a trivial heuristic.
    """
    if not XAI_KEY:
        t = text.lower()
        pos = sum(w in t for w in ["great","bull","pump","strong","optimistic","up"])
        neg = sum(w in t for w in ["bad","bear","dump","weak","fear","down"])
        score = (pos - neg) / 3.0
        return max(-1.0, min(1.0, score))

    # Example stub (adjust URL/payload for your xAI provider)
    url = "https://api.x.ai/sentiment"  # placeholder
    headers = {"Authorization": f"Bearer {XAI_KEY}"}
    payload = {"text": text}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        return float(js.get("score", 0.0))
    except Exception:
        # graceful degrade
        return 0.0
