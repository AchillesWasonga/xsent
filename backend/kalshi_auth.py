import os, time, base64, json, requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv, find_dotenv

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

load_dotenv(find_dotenv())

KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID") or os.getenv("KALSHI_API_KEY") or os.getenv("KALSHI_API_KEY_ID".upper())
KALSHI_PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH", "kalpr.txt")
KALSHI_BASE = os.getenv("KALSHI_BASE_URL", "https://api.kalshi.com/trade-api/v2")

if not KALSHI_API_KEY_ID:
    raise RuntimeError("KALSHI_API_KEY_ID missing in .env")
if not os.path.exists(KALSHI_PRIVATE_KEY_PATH):
    raise RuntimeError(f"Kalshi private key file not found: {KALSHI_PRIVATE_KEY_PATH}")

def _load_private_key():
    with open(KALSHI_PRIVATE_KEY_PATH, "rb") as f:
        key_data = f.read()
    return serialization.load_pem_private_key(key_data, password=None, backend=default_backend())

def _sign(method: str, path: str, body: bytes, ts_ms: int) -> str:
    """
    Kalshi uses RSA-PSS(SHA256). Canonical message pattern commonly used:
    f"{ts_ms}{method.upper()}{path}{body.decode() if body else ''}".encode()
    If you get 401, check Kalshi docs for any canonicalization tweaks.
    """
    msg = f"{ts_ms}{method.upper()}{path}".encode() + (body or b"")
    sk = _load_private_key()
    signature = sk.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()

def kalshi_request(method: str, url_path: str, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = json.dumps(json_body).encode() if json_body is not None else b""
    ts = int(time.time() * 1000)
    sig = _sign(method, url_path, body, ts)

    headers = {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": str(ts),
        "KALSHI-ACCESS-SIGNATURE": sig,
        "Content-Type": "application/json",
    }
    resp = requests.request(method, f"{KALSHI_BASE}{url_path}", headers=headers, json=json_body, timeout=20)
    if resp.status_code >= 400:
        raise RuntimeError(f"Kalshi error {resp.status_code}: {resp.text}")
    return resp.json()

def list_open_markets() -> Dict[str, Any]:
    # Example: filter for open markets (adjust filters as needed)
    return kalshi_request("GET", "/markets?filter[status]=OPEN")
