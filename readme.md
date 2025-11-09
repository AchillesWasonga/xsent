# xSent — X → Sentiment → Kalshi Signals

xSent turns real-time social chatter into trading hints.
It pulls recent posts from **X (Twitter)** for a topic, scores each post’s tone using **xAI (Grok)**, aggregates a sentiment signal and (optionally) sends a **signed** order to the **Kalshi Elections Trade API**. The Streamlit front-end lets you analyze a topic, browse active Kalshi markets, see a toy YES/NO/HOLD suggestion, simulate or place a real order.

---

## Features

* 🔎 Fetch recent posts on a query from X API v2
* 🧠 Call xAI (Grok) for sentiment, aggregate average + counts
* 📈 Streamlit dashboard with charts & suggested action (YES/NO/HOLD)
* 🗳️ Browse **Kalshi Elections** markets and (optionally) place a signed order
* 🛡️ Safe fallback behavior (rate-limit on X → demo tweets; strict key handling)

---

## Repo layout

```
xsent/
├─ backend/
│  ├─ app.py            # FastAPI server (endpoints for frontend)
│  ├─ x_fetcher.py      # X API v2 recent search
│  ├─ xai_client.py     # xAI (Grok) sentiment calls
│  ├─ aggregator.py     # combine scores -> average + rule
│  └─ kalshi_auth.py    # RSA-PSS signing + Elections API calls
├─ frontend/
│  └─ streamlit_app.py  # Streamlit UI
├─ .env                 # your local env vars (not committed)
├─ kalpr.txt            # your Kalshi private key (PEM, not committed)
└─ requirements.txt
```

---

## Requirements

* **Python 3.9+**
* macOS/Linux (Windows works with minor path tweaks)
* An **X (Twitter) developer account** (Free/Basic/Pro), with API v2 keys
* An **xAI (Grok) API key**
* A **Kalshi Elections** API key pair (Key ID + RSA private key in PEM)
* Internet access (if on campus/VPN, allow access to `api.elections.kalshi.com` and X API)

---

## Keys you need (and what to name them)

Create a file named **`.env`** in the repo root with:

```env
# xAI (Grok)
XAI_KEY=your_xai_api_key

# X (Twitter) API v2
X_API_KEY=your_x_api_key
X_API_SECRET=your_x_api_secret
X_BEARER=your_x_bearer_token

# Kalshi Elections
KALSHI_API_KEY_ID=your_kalshi_key_id
KALSHI_PRIVATE_KEY=kalpr.txt   # path to your PEM (relative or absolute)


```

> ⚠️ **Do not** commit `.env` or your private key. The repo’s `.gitignore` already ignores them.

Save your **Kalshi private key** PEM as **`kalpr.txt`** in the repo root (or change the path in `.env`).
Kalshi Elections base host used by the backend: **`https://api.elections.kalshi.com`**.
**When signing requests we sign only the path (without query)** as required by Kalshi.

---

## Setup

```bash
# 1) Clone
git clone https://github.com/AchillesWasonga/xsent
cd xsent

# 2) Create & activate a virtualenv
python3 -m venv xvir
source xvir/bin/activate  # Windows: xvir\Scripts\activate

# 3) Install deps
pip install -r requirements.txt

# 4) Add your keys
#    - Put your .env in repo root (see above)
#    - Put your Kalshi PEM in kalpr.txt (or update KALSHI_PRIVATE_KEY path)
```

---

## Run it

### 1) Start the backend (FastAPI)

```bash
uvicorn backend.app:app --reload
```

* Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* Endpoints used by the UI:

  * `GET /api/sentiment?q=<query>&max_results=<n>`
  * `GET /api/kalshi/markets`
  * `POST /api/kalshi/order` (JSON: `{ticker, side("buy"/"sell"), price(1..99), count}`)

### 2) Start the frontend (Streamlit)

In a **new** terminal (same venv):

```bash
streamlit run frontend/streamlit_app.py
```

Open: [http://localhost:8501](http://localhost:8501)
Make sure the left sidebar **Backend URL** is `http://127.0.0.1:8000`.

---

## How to use (demo flow)

1. In **Analyze** tab: type a topic (e.g., `bitcoin`) → **Analyze Sentiment**

   * We fetch recent posts from X, score via xAI, and compute an average.

2. Go to **Markets & Trade** tab:

   * Browse **Kalshi Elections** markets (loaded from the Elections API).
   * The panel shows a **toy rule** (YES/NO/HOLD) based on average sentiment and counts.
   * You can **Simulate** or **Place Order** (requires real Kalshi credentials and funds).

> The “toy rule” is intentionally simple:
>
> * `YES` if avg ≥ +0.15 and positive ≥ 2×negative
> * `NO`  if avg ≤ −0.15 and negative ≥ 2×positive
> * otherwise `HOLD`

---

## Troubleshooting

* **X API 429 (Too Many Requests)**
  You’re on Free/Basic plan or hit per-minute caps. The backend logs a back-off and then uses fallback demo tweets. Upgrade plan or lower `max_results`.

* **Kalshi unreachable / DNS errors**
  Ensure you’re calling **`api.elections.kalshi.com`** (not `api.kalshi.com`).
  Check DNS/VPN:

  ```bash
  nslookup api.elections.kalshi.com 1.1.1.1
  ```

* **Kalshi signature errors**
  We sign `timestamp + METHOD + PATH` (no query). Verify your PEM and that `KALSHI_PRIVATE_KEY` points to it.

* **LibreSSL / urllib3 warning on macOS**
  It’s a warning from system Python SSL. The app still runs. If desired, use Homebrew’s Python or a newer Python build.

* **Streamlit not found**
  Make sure you’re in the venv and installed `requirements.txt`.

---

## Security notes

* Never commit `.env` or private keys.
* Keep your Kalshi PEM file secure; treat it like a password.
* Orders are **real** when you click “Place Order”. Use a small quantity.

---

## What’s next (roadmap ideas)

* Get more X credits for more tests and improvements or upgrade to a better plan

