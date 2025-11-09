# backend/kalshi_auth.py
import os, time, base64, requests
from typing import Optional, Dict, Any      # ← add
from urllib.parse import urlsplit
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

KALSHI_BASE = os.getenv("KALSHI_HOST", "https://api.elections.kalshi.com").rstrip("/")
KALSHI_KEY_ID = os.getenv("KALSHI_API_KEY_ID", "").strip()
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY", "kalpr.txt")

def _load_private_key():
    with open(KALSHI_PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

def _sign_pss_text(priv: rsa.RSAPrivateKey, text: str) -> str:
    sig = priv.sign(
        text.encode("utf-8"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("utf-8")

def _signed_headers(method: str, full_url: str) -> Dict[str, str]:
    ts_ms = str(int(time.time() * 1000))
    path_only = urlsplit(full_url).path                  # sign PATH ONLY
    msg = ts_ms + method.upper() + path_only
    sig = _sign_pss_text(_load_private_key(), msg)
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": ts_ms,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "Content-Type": "application/json",
    }

def kalshi_request(method: str, path: str, json_body: Optional[Dict[str, Any]] = None, timeout: int = 20):  # ← change
    if not path.startswith("/"):
        path = "/" + path
    url = f"{KALSHI_BASE}{path}"
    headers = _signed_headers(method, url)
    r = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
    r.raise_for_status()
    return r.json()

def list_open_markets():
    return kalshi_request("GET", "/trade-api/v2/markets?filter[status]=OPEN")

def get_balance():
    return kalshi_request("GET", "/trade-api/v2/portfolio/balances")

def place_order(market_ticker: str, side: str, price: int, quantity: int):
    body = {
        "ticker": market_ticker,
        "type": "limit",
        "side": side.lower(),
        "price": int(price),
        "count": int(quantity),
        "time_in_force": "gtc",
    }
    return kalshi_request("POST", "/trade-api/v2/portfolio/orders", json_body=body)
