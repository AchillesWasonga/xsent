# frontend/streamlit_app.py
import os
import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from functools import lru_cache

# -------------------- Config --------------------
DEFAULT_BACKEND = os.getenv("XSENT_BACKEND", "http://127.0.0.1:8000").rstrip("/")
st.set_page_config(page_title="xSent — X → Sentiment → Kalshi Signals", layout="wide")

st.markdown("""
<style>
.small { font-size: 0.9rem; opacity: 0.75; }
.badge { padding:2px 8px; border-radius: 999px; font-weight:600; display:inline-block; }
.badge-live { background:#e6ffed; color:#067d3b; border:1px solid #a8f0c2; }
.badge-demo { background:#fff7ed; color:#9a3412; border:1px solid #fed7aa; }
.badge-err { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.badge-pos { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.badge-neg { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.badge-neu { background:#eef2ff; color:#1e3a8a; border:1px solid #c7d2fe; }
.sig-YES { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.sig-NO { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.sig-HOLD { background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
</style>
""", unsafe_allow_html=True)

# -------------------- Sidebar --------------------
with st.sidebar:
    st.header("Backend")
    BACKEND = st.text_input("Backend URL", value=DEFAULT_BACKEND, help="Your FastAPI base URL").rstrip("/")
    st.caption("Run: `uvicorn backend.app:app --reload`")
    st.divider()
    st.header("Auto-Sync")
    auto = st.toggle("Refresh UI every 5s", value=False, help="(front-end only; avoids hammering APIs)")
    st.caption("If Markets don’t load, ensure your backend can reach `api.elections.kalshi.com` and that your Kalshi env vars are set.")

# -------------------- API helpers --------------------
def _err_msg(e: requests.HTTPError) -> str:
    try:
        return e.response.text[:500]
    except Exception:
        return str(e)

def _get(url, **kwargs):
    r = requests.get(url, timeout=kwargs.pop("timeout", 60), **kwargs)
    r.raise_for_status()
    return r.json()

def _post(url, **kwargs):
    r = requests.post(url, timeout=kwargs.pop("timeout", 60), **kwargs)
    r.raise_for_status()
    return r.json()

def run_sentiment(backend: str, query: str, max_results: int = 20):
    return _get(f"{backend}/api/sentiment", params={"q": query, "max_results": int(max_results)}, timeout=90)

@lru_cache(maxsize=64)
def fetch_markets(backend: str):
    data = _get(f"{backend}/api/kalshi/markets", timeout=30)
    # Support both direct lists and {"markets":[...]} shapes
    return data.get("markets", data.get("data", data))

def place_live_order(backend: str, ticker: str, side: str, price: int, count: int):
    payload = {"ticker": ticker, "side": side.lower(), "price": int(price), "count": int(count)}
    return _post(f"{backend}/api/kalshi/order", json=payload, timeout=30)

# -------------------- Recommendation rule --------------------
def sentiment_recommendation(avg: float, pos: int, neg: int):
    """
    Toy demo rule:
      avg >= +0.15 and pos >= 2*neg  -> YES (confidence ~ avg)
      avg <= -0.15 and neg >= 2*pos  -> NO  (confidence ~ |avg|)
      else HOLD
    """
    if avg >= 0.15 and pos >= 2 * max(1, neg):
        return ("YES", min(0.99, round(avg, 3)), 60)
    if avg <= -0.15 and neg >= 2 * max(1, pos):
        return ("NO", min(0.99, round(abs(avg), 3)), 60)
    return ("HOLD", 0.3, 50)

# -------------------- UI Tabs --------------------
st.title("xSent — X → Sentiment → Kalshi Signals")
tabs = st.tabs(["🔎 Analyze", "📈 Markets & Trade", "ℹ️ About"])

# ========== Analyze ==========
with tabs[0]:
    st.subheader("Analyze X sentiment")

    qcol, mcol = st.columns([4,1.2])
    with qcol:
        query = st.text_input("Topic or query", value="bitcoin", placeholder="e.g., bitcoin, CPI, election, 'OpenAI -is:retweet'")
    with mcol:
        max_results = st.number_input("Max tweets", min_value=1, max_value=300, value=30, step=5)

    if st.button("Analyze Sentiment", type="primary"):
        try:
            data = run_sentiment(BACKEND, query, max_results)
            st.session_state["last_query"] = query
            st.session_state["last_data"] = data
            st.success("Analysis complete.")
        except requests.HTTPError as e:
            st.error(_err_msg(e))
        except Exception as e:
            st.error(str(e))

    if "last_data" in st.session_state:
        data = st.session_state["last_data"]
        src = data.get("source", "UNKNOWN")
        avg = float(data.get("avg_score", 0.0))
        counts = data.get("counts", {})
        pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)
        n, req = data.get("n", 0), data.get("requested", 0)

        badge = "badge-live" if src == "LIVE" else ("badge-demo" if src == "DEMO" else "badge-err")
        st.markdown(
            f"**Avg Sentiment:** {avg:+.3f} &nbsp;"
            f"<span class='badge badge-pos'>+{pos}</span> "
            f"<span class='badge badge-neg'>-{neg}</span> "
            f"<span class='badge badge-neu'>±{neu}</span> &nbsp;|&nbsp; "
            f"**Items:** {n} / requested {req} &nbsp;|&nbsp; "
            f"Source: <span class='badge {badge}'>{src}</span>",
            unsafe_allow_html=True
        )

        items = data.get("items", [])
        if items:
            df = pd.DataFrame([{
                "tweet_id": x.get("id"),
                "score": x.get("score"),
                "label": x.get("label"),
                "text": x.get("text", ""),
            } for x in items])
            st.dataframe(df, use_container_width=True, hide_index=True)

            if "score" in df:
                fig = px.histogram(df, x="score", nbins=30, title="Sentiment score distribution")
                st.plotly_chart(fig, use_container_width=True)

# ========== Markets & Trade ==========
with tabs[1]:
    left, right = st.columns([3,2])

    with left:
        st.subheader("Browse Kalshi Markets")
        try:
            mkts = fetch_markets(BACKEND)
        except requests.HTTPError as e:
            st.error(_err_msg(e)); mkts = []
        except Exception as e:
            st.error(str(e)); mkts = []

        if mkts:
            options = []
            for m in mkts:
                title = m.get("title") or m.get("question") or m.get("ticker") or "untitled"
                ticker = m.get("ticker")
                if ticker:
                    options.append((title, ticker))
            lbls = [o[0] for o in options]
            tickers = {o[0]: o[1] for o in options}
            choice = st.selectbox("Select a market", lbls) if lbls else None
            chosen_ticker = tickers.get(choice) if choice else None
            if chosen_ticker:
                st.caption(f"Ticker: `{chosen_ticker}`")

            st.divider()
            st.write("**Link sentiment to this market (optional)**")
            market_query = st.text_input("Market-specific query", value=(choice or ""))
            mq_results = st.number_input("Tweets for market query", 1, 200, 20, step=5)
            if st.button("Analyze Market Query"):
                try:
                    mdata = run_sentiment(BACKEND, market_query, mq_results)
                    st.session_state["market_data"] = mdata
                    st.success("Market query analyzed.")
                except Exception as e:
                    st.error(str(e))

            if "market_data" in st.session_state:
                mdata = st.session_state["market_data"]
                msrc = mdata.get("source", "UNKNOWN")
                mavg = float(mdata.get("avg_score", 0.0))
                mcounts = mdata.get("counts", {})
                mpos, mneg, mneu = mcounts.get("pos", 0), mcounts.get("neg", 0), mcounts.get("neu", 0)
                mbadge = "badge-live" if msrc == "LIVE" else ("badge-demo" if msrc == "DEMO" else "badge-err")
                st.markdown(
                    f"**Avg:** {mavg:+.3f} &nbsp;"
                    f"<span class='badge badge-pos'>+{mpos}</span> "
                    f"<span class='badge badge-neg'>-{mneg}</span> "
                    f"<span class='badge badge-neu'>±{mneu}</span> &nbsp;|&nbsp; "
                    f"Source: <span class='badge {mbadge}'>{msrc}</span>",
                    unsafe_allow_html=True
                )

    with right:
        st.subheader("Signal & Order")

        # Prefer market_data if present, else last_data
        data = st.session_state.get("market_data") or st.session_state.get("last_data")
        if not data:
            st.info("Run an analysis in the Analyze tab (or Market-specific) to generate a signal.")
        else:
            avg = float(data.get("avg_score", 0.0))
            counts = data.get("counts", {})
            pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)
            side, conf, price_hint = sentiment_recommendation(avg, pos, neg)
            st.markdown(
                f"**Model Recommendation:** "
                f"<span class='badge sig-{side}'>{side}</span> "
                f"<span class='small'>&nbsp;confidence {int(conf*100)}%</span>",
                unsafe_allow_html=True
            )

            st.divider()
            st.write("### Place order (Kalshi)")
            order_side = st.selectbox("Side", ["YES", "NO"], index=0 if side=="YES" else (1 if side=="NO" else 0))
            price = st.slider("Limit price (¢)", 1, 99, price_hint)
            qty = st.number_input("Quantity", 1, 100, 1)
            chosen_ticker = None
            # recover ticker from left column selection by searching cache (quick hack)
            try:
                mkts = fetch_markets(BACKEND)
                if mkts:
                    titles = [m.get("title") or m.get("question") or m.get("ticker") for m in mkts]
                    # best-effort: if user selected earlier, it's stored in the left column; otherwise we let user type
            except Exception:
                pass
            manual_ticker = st.text_input("Ticker (paste from Markets list)", value="")

            c1, c2 = st.columns(2)
            if c1.button("Simulate"):
                st.success(f"SIM: {order_side} {qty} @ {price}¢ on {(manual_ticker or '—')}")

            if c2.button("Place Order", type="primary", disabled=not manual_ticker):
                try:
                    side_map = {"YES": "buy", "NO": "sell"}
                    resp = place_live_order(BACKEND, manual_ticker, side_map[order_side], int(price), int(qty))
                    st.success(f"Order response: {resp}")
                except requests.HTTPError as e:
                    st.error(_err_msg(e))
                except Exception as e:
                    st.error(str(e))

# ========== About ==========
with tabs[2]:
    st.markdown("""
**xSent** reads live social sentiment from **X (Twitter)** and turns it into simple **Kalshi** trading hints.
- **LIVE/DEMO badge** tells you whether results are from the real API or a demo set.
- If you hit rate limits, try fewer tweets or wait a minute.
- Env keys used (from `.env` or shell):
  - `X_BEARER` (required for X)
  - `X_API_KEY` and `X_API_SECRET` (optional here; bearer is used for search)
  - `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY`, `KALSHI_HOST` (for orders/markets)

> This is a hackathon demo; the trading rule is intentionally simple. Tweak freely.
""")
