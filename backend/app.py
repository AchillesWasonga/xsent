# backend/app.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.aggregator import analyze_topic
from backend.kalshi_auth import list_open_markets, get_balance, place_order

APP_NAME = "xSent Backend"

app = FastAPI(title=APP_NAME)

# CORS for local Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "name": APP_NAME}

# ---- Sentiment ----
@app.get("/api/sentiment")
def api_sentiment(q: str, max_results: int = 10):
    try:
        # guardrails
        max_results = max(1, min(50, int(max_results)))
        return analyze_topic(q, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Kalshi ----
@app.get("/api/kalshi/markets")
def api_kalshi_markets():
    try:
        return list_open_markets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kalshi/balance")
def api_kalshi_balance():
    try:
        return get_balance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OrderIn(BaseModel):
    ticker: str
    side: str   # "buy" or "sell"
    price: int  # 1..99
    count: int  # contracts

@app.post("/api/kalshi/order")
def api_kalshi_order(o: OrderIn):
    try:
        return place_order(o.ticker, o.side, int(o.price), int(o.count))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
