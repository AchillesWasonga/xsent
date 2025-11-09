# frontend/streamlit_app.py
import os, requests, time
import pandas as pd
import plotly.express as px
import streamlit as st
from functools import lru_cache

DEFAULT_BACKEND = os.getenv("XSENT_BACKEND", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="xSent — X → Sentiment → Kalshi Signals", layout="wide")
st.markdown("""
<style>
.small { font-size: 0.9rem; opacity: 0.85; }
.badge { padding:2px 8px; border-radius: 999px; font-weight:600; }
.badge-pos { background:#e6ffed; color:#067d3b; border:1px solid #a8f0c2; }
.badge-neg { background:#ffecec; color:#b00020; border:1px solid #ffb3b3; }
.badge-neu { background:#eef2ff; color:#1e3a8a; border:1px solid #c7d2fe; }
.sig-yes { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.sig-no  { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.sig-hold{ background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
</style>
""", unsafe_allow_html=True)

# ---------- helpers ----------
def backend_url_input():
    with st.sidebar:
        st.header("Backend")
        be = st.text_input("Backend URL", value=DEFAULT_BACKEND, help="Your FastAPI base URL")
        st.caption("Run: `uvicorn backend.app:app --reload`")
        st.divider()
        auto = st.toggle("Refresh UI every 5s", value=False, help="Light auto-refresh while working")
        if auto:
            st.session_state["_tick"] = st.session_state.get("_tick", 0) + 1
            time.sleep(5)
            st.experimental_rerun()
        return be.rstrip("/")

@lru_cache(maxsize=64)
def fetch_markets(backend: str):
    r = requests.get(f"{backend}/api/kalshi/markets", timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("markets", data.get("data", data))

def run_sentiment(backend: str, query: str, max_results: int = 10):
    r = requests.get(
        f"{backend}/api/sentiment",
        params={"q": query, "max_results": max_results},
        timeout=180,  # be generous; backend has its own time budget
    )
    r.raise_for_status()
    return r.json()

def place_live_order(backend: str, ticker: str, side: str, price: int, count: int):
    payload = {"ticker": ticker, "side": side.lower(), "price": int(price), "count": int(count)}
    r = requests.post(f"{backend}/api/kalshi/order", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def sentiment_recommendation(avg: float, pos: int, neg: int):
    if avg >= 0.15 and pos >= 2 * max(1, neg):
        return ("YES", min(0.99, round(avg, 3)), 60)
    if avg <= -0.15 and neg >= 2 * max(1, pos):
        return ("NO", min(0.99, round(abs(avg), 3)), 60)
    return ("HOLD", 0.3, 50)

# ---------- UI ----------
BACKEND = backend_url_input()
st.title("xSent — X → Sentiment → Kalshi Signals")

tabs = st.tabs(["🔎 Analyze", "📈 Markets & Trade", "ℹ️ About"])

# Analyze
with tabs[0]:
    st.subheader("Analyze X sentiment")
    qc, mc = st.columns([3,1])
    with qc:
        query = st.text_input("Topic or query", value="bitcoin", placeholder="try a company, event, or asset")
    with mc:
        max_results = st.number_input("Max tweets", min_value=1, max_value=50, value=10)

    if st.button("Analyze Sentiment", type="primary"):
        with st.spinner("Scoring tweets…"):
            try:
                data = run_sentiment(BACKEND, query, int(max_results))
                st.session_state["last_query"] = query
                st.session_state["last_data"] = data
                st.success("Analysis complete.")
            except requests.HTTPError as e:
                st.error(f"Backend error: {e.response.text[:300]}")
            except Exception as e:
                st.error(f"Error: {e}")

    if "last_data" in st.session_state:
        data = st.session_state["last_data"]
        avg = float(data.get("avg_score", 0.0))
        counts = data.get("counts", {})
        pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)

        st.markdown(
            f"**Avg Sentiment:** {avg:+.3f} &nbsp; "
            f"<span class='badge badge-pos'>+{pos}</span> "
            f"<span class='badge badge-neg'>-{neg}</span> "
            f"<span class='badge badge-neu'>±{neu}</span>",
            unsafe_allow_html=True
        )

        items = data.get("items", [])
        if items:
            df = pd.DataFrame([{
                "tweet_id": x.get("id"),
                "score": x.get("score"),
                "label": x.get("label"),
                "text": (x.get("text") or "")[:180] + ("…" if len(x.get("text",""))>180 else "")
            } for x in items])

            st.dataframe(df, hide_index=True, use_container_width=True)
            st.plotly_chart(px.histogram(df, x="score", nbins=20, title="Sentiment score distribution"),
                            use_container_width=True)

# Markets & Trade
with tabs[1]:
    lc, rc = st.columns([3,2])
    with lc:
        st.subheader("Browse Kalshi Markets")
        try:
            mkts = fetch_markets(BACKEND)
        except Exception as e:
            st.error(f"Could not load markets: {e}")
            mkts = []

        chosen_ticker = None
        if mkts:
            opts = [(m.get("title") or m.get("ticker") or "untitled", m.get("ticker")) for m in mkts if m.get("ticker")]
            labels = [o[0] for o in opts]
            mapping = {o[0]: o[1] for o in opts}
            choice = st.selectbox("Select a market", labels)
            chosen_ticker = mapping.get(choice)
            if chosen_ticker:
                st.caption(f"Ticker: `{chosen_ticker}`")

    with rc:
        st.subheader("Signal & Order")
        if "last_data" not in st.session_state:
            st.info("Run an analysis on the **Analyze** tab to generate a signal.")
        else:
            data = st.session_state["last_data"]
            avg = float(data.get("avg_score", 0.0))
            counts = data.get("counts", {})
            pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)
            side, conf, price_hint = sentiment_recommendation(avg, pos, neg)

            badge_cls = "sig-yes" if side=="YES" else ("sig-no" if side=="NO" else "sig-hold")
            st.markdown(
                f"**Avg:** {avg:+.3f} &nbsp; "
                f"<span class='badge {badge_cls}'>Recommendation: {side}</span> "
                f"&nbsp;<span class='small'>(confidence {int(conf*100)}%)</span>",
                unsafe_allow_html=True
            )

            st.divider()
            st.write("### Order Parameters")
            oc1, oc2 = st.columns(2)
            with oc1:
                order_side = st.selectbox("Side", ["YES", "NO"], index=0 if side=="YES" else (1 if side=="NO" else 0))
                price = st.slider("Limit price (¢)", 1, 99, price_hint)
            with oc2:
                qty = st.number_input("Quantity (contracts)", 1, 100, 1)
                confirm = st.checkbox("I understand this may place a real order", value=False)

            c1, c2 = st.columns(2)
            if c1.button("💡 Simulate"):
                st.success(f"SIM: {order_side} {qty} @ {price}¢ on {chosen_ticker or '(pick a market)'}")

            if c2.button("🚀 Place Order", type="primary", disabled=not (confirm and chosen_ticker)):
                try:
                    side_map = {"YES": "buy", "NO": "sell"}
                    resp = place_live_order(BACKEND, chosen_ticker, side_map[order_side], int(price), int(qty))
                    st.success(f"Order response: {resp}")
                except requests.HTTPError as e:
                    st.error(f"Order failed: {e.response.text[:400]}")
                except Exception as e:
                    st.error(f"Order failed: {e}")

# About
with tabs[2]:
    st.markdown("""
**xSent** turns **X** (Twitter) sentiment into simple **Kalshi** trading signals.
1) Fetch recent posts from X for your query  
2) Score with xAI (or fallback heuristic)  
3) Convert to a YES/NO/HOLD rule  
4) Browse markets and simulate/place orders
""")
