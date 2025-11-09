# backend/app.py
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

# Load .env early
load_dotenv(find_dotenv())

# Local modules
from backend.aggregator import analyze_topic
from backend.kalshi_auth import list_open_markets, get_balance, place_order

app = FastAPI(title="xSent API", version="0.1.0")

# Allow Streamlit (localhost:8501) + same-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8501",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "ok": True,
        "xai_key": bool(os.getenv("XAI_KEY")),
        "x_bearer": bool(os.getenv("X_BEARER")),
        "kalshi_key": bool(os.getenv("KALSHI_API_KEY_ID")),
    }

# ---------------- Sentiment ----------------

@app.get("/api/sentiment")
def api_sentiment(
    q: str = Query(..., description="Topic to search on X"),
    max_results: int = Query(10, ge=1, le=100),
):
    """
    Fetch recent posts from X (using your X_* creds),
    score them with xAI (XAI_KEY), and aggregate.
    """
    try:
        return analyze_topic(q, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sentiment error: {e}")

# ---------------- Kalshi ----------------

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
    side: str      # "buy" or "sell"
    price: int     # 1..99
    count: int

@app.post("/api/kalshi/order")
def api_kalshi_order(o: OrderIn):
    try:
        return place_order(o.ticker, o.side, o.price, o.count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
