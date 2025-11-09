# backend/kalshi_auth.py
import os, time, base64, requests
from urllib.parse import urlsplit
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

# -------- base URL (elections host) --------
# Keeps life simple: include /trade-api/v2 in the base, pass short paths like "/markets?status=open"
KALSHI_BASE = os.getenv(
    "KALSHI_API_BASE",
    "https://api.elections.kalshi.com/trade-api/v2"
).rstrip("/")

# -------- env names you use (with safe fallbacks) --------
KALSHI_KEY_ID = (os.getenv("KALSHI_API_KEY_ID") or os.getenv("KALSHI_KEY_ID") or "").strip()
KALSHI_PRIVATE_KEY = os.getenv("KALSHI_PRIVATE_KEY", "").strip()  # path OR inline PEM
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalpr.txt").strip()

def _load_private_key() -> rsa.RSAPrivateKey:
    """
    Load the RSA private key.
    - If KALSHI_PRIVATE_KEY looks like PEM ('-----BEGIN'), treat it as inline PEM.
    - Otherwise treat KALSHI_PRIVATE_KEY as a path.
    - If empty, fall back to KALSHI_PRIVATE_KEY_PATH.
    """
    if KALSHI_PRIVATE_KEY:
        if KALSHI_PRIVATE_KEY.startswith("-----BEGIN"):
            pem_bytes = KALSHI_PRIVATE_KEY.encode("utf-8")
        else:
            with open(KALSHI_PRIVATE_KEY, "rb") as f:
                pem_bytes = f.read()
    else:
        with open(KALSHI_PRIVATE_KEY_PATH, "rb") as f:
            pem_bytes = f.read()

    return serialization.load_pem_private_key(pem_bytes, password=None, backend=default_backend())

def _sign_pss_text(priv: rsa.RSAPrivateKey, text: str) -> str:
    sig = priv.sign(
        text.encode("utf-8"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("utf-8")

def _signed_headers(method: str, full_url: str) -> dict:
    if not KALSHI_KEY_ID:
        raise RuntimeError("Missing KALSHI_API_KEY_ID (or KALSHI_KEY_ID) in environment")
    ts_ms = str(int(time.time() * 1000))
    # IMPORTANT: sign only the PATH (no query string)
    path_only = urlsplit(full_url).path
    msg = ts_ms + method.upper() + path_only
    sig = _sign_pss_text(_load_private_key(), msg)
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": ts_ms,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "Content-Type": "application/json",
    }

def kalshi_request(method: str, path: str, json_body: Optional[dict] = None, timeout: int = 20):
    url = f"{KALSHI_BASE}{path}"
    headers = _signed_headers(method, url)
    r = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ---------- Convenience wrappers ----------
def list_open_markets():
    # Public list (no auth required by Kalshi for market data), but signing is fine.
    # Use 'status=open' (lowercase) – compatible with the elections host.
    return kalshi_request("GET", "/markets?status=open")

def get_balance():
    return kalshi_request("GET", "/portfolio/balance")

def place_order(market_ticker: str, side: str, price: int, quantity: int):
    """
    side: 'buy' or 'sell'
    price: 1..99 (cents)
    quantity: integer number of contracts
    """
    body = {
        "ticker": market_ticker,
        "type": "limit",
        "side": side.lower(),       # "buy" or "sell"
        "price": int(price),
        "count": int(quantity),
        "time_in_force": "gtc",
    }
    return kalshi_request("POST", "/portfolio/orders", json_body=body)
