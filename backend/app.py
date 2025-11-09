from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from backend.aggregator import analyze_topic
from backend.kalshi_auth import list_open_markets

app = FastAPI(title="XSent Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/sentiment")
def api_sentiment(q: str = Query("bitcoin", min_length=1), max_results: int = 25):
    return analyze_topic(q, max_results=max_results)

@app.get("/api/kalshi/markets")
def api_kalshi_markets():
    # requires proper Kalshi key + private key file
    return list_open_markets()
