# backend/app.py
from __future__ import annotations

import os
import traceback
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Load .env at process start
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from backend.aggregator import analyze_topic
from backend.kalshi_auth import list_open_markets, get_balance, place_order

app = FastAPI(title="xSent Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

# --- Debug helper: confirm env vars are visible (masks secrets) ---
@app.get("/debug/env")
def debug_env():
    def mask(v: Optional[str]) -> str:
        if not v:
            return ""
        if len(v) <= 8:
            return "***"
        return v[:4] + "…" + v[-4:]

    return {
        "XSENT_FORCE_DEMO": os.getenv("XSENT_FORCE_DEMO", "0"),
        "X_BEARER": mask(os.getenv("X_BEARER")),
        "KALSHI_HOST": os.getenv("KALSHI_HOST"),
        "KALSHI_API_KEY_ID": mask(os.getenv("KALSHI_API_KEY_ID")),
        "KALSHI_PRIVATE_KEY": os.getenv("KALSHI_PRIVATE_KEY"),
    }

# --- Sentiment ---
@app.get("/api/sentiment")
def api_sentiment(
    q: str = Query(..., min_length=1),
    max_results: int = Query(10, ge=1, le=300),
):
    try:
        return analyze_topic(q, max_results=max_results, lang="en")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- Kalshi: list markets ---
@app.get("/api/kalshi/markets")
def api_kalshi_markets():
    try:
        return list_open_markets()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- Kalshi: balance ---
@app.get("/api/kalshi/balance")
def api_kalshi_balance():
    try:
        return get_balance()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- Kalshi: place order ---
from pydantic import BaseModel

class OrderIn(BaseModel):
    ticker: str
    side: str      # "buy" or "sell"  (your YES/NO mapping happens in the UI)
    price: int     # 1..99
    count: int

@app.post("/api/kalshi/order")
def api_kalshi_order(o: OrderIn):
    try:
        return place_order(o.ticker, o.side, o.price, o.count)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
