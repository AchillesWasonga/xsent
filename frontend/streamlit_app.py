# frontend/streamlit_app.py
import os
import time
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------- Page / Styles -------------------
st.set_page_config(page_title="xSent — X → Sentiment → Kalshi Signals", layout="wide")

st.markdown("""
<style>
.small { font-size: 0.9rem; opacity: 0.8; }
.badge { padding:2px 10px; border-radius: 999px; font-weight:600; }
.badge-pos { background:#e6ffed; color:#067d3b; border:1px solid #a8f0c2; }
.badge-neg { background:#ffecec; color:#b00020; border:1px solid #ffb3b3; }
.badge-neu { background:#eef2ff; color:#1e3a8a; border:1px solid #c7d2fe; }
.sig-yes { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.sig-no  { background:#fee2e2; color:#991b1b; border:1px solid #fecaca; }
.sig-hold{ background:#e5e7eb; color:#374151; border:1px solid #d1d5db; }
.sidebar-note { font-size:0.85rem; opacity:0.8; line-height:1.3; }
hr { border-color: #222; }
</style>
""", unsafe_allow_html=True)

# ------------------- Auto-refresh helper -------------------
def enable_auto_sync(seconds: int = 5, key: str = "xsent_last_refresh"):
    """Simple built-in timer refresher for older Streamlit versions."""
    if st.session_state.get("auto_sync", False):
        now = time.time()
        last = st.session_state.get(key, 0)
        if now - last >= seconds:
            st.session_state[key] = now
            st.experimental_rerun()

# ------------------- Defaults / Session -------------------
DEFAULT_BACKEND = os.getenv("XSENT_BACKEND", "http://127.0.0.1:8000").rstrip("/")

for k, v in {
    "last_query": "bitcoin",
    "last_data": None,
    "selected_market_label": None,
    "selected_market_ticker": None,
    "auto_sync": False,
    "markets_cache_ts": 0,
    "markets_cache": []
}.items():
    st.session_state.setdefault(k, v)

# ------------------- Sidebar -------------------
with st.sidebar:
    st.header("Backend")
    BACKEND = st.text_input("Backend URL", value=DEFAULT_BACKEND, help="Your FastAPI server base URL").rstrip("/")
    st.caption("Make sure your backend is running:\n`uvicorn backend.app:app --reload`")

    st.markdown("---")
    st.header("Auto-Sync")
    st.session_state["auto_sync"] = st.toggle(
        "Refresh UI every 5s",
        value=st.session_state["auto_sync"],
        help="Keeps Markets list and Signal panel in sync without manual refresh."
    )
    if st.session_state["auto_sync"]:
        enable_auto_sync(5)

    st.markdown("---")
    st.markdown(
        "<div class='sidebar-note'>Tip: if Markets don’t load, confirm your "
        "backend can reach <code>api.elections.kalshi.com</code> and your Kalshi env "
        "vars/keys are set.</div>", unsafe_allow_html=True
    )

# ------------------- HTTP helpers -------------------
def _get(url, **kw):
    r = requests.get(url, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r.json()

def _post(url, **kw):
    r = requests.post(url, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r.json()

def fetch_markets_cached(backend: str, ttl_sec: int = 30):
    now = time.time()
    if now - st.session_state["markets_cache_ts"] < ttl_sec and st.session_state["markets_cache"]:
        return st.session_state["markets_cache"]
    try:
        data = _get(f"{backend}/api/kalshi/markets")
        mkts = data.get("markets", data.get("data", data))
        if isinstance(mkts, list):
            st.session_state["markets_cache"] = mkts
            st.session_state["markets_cache_ts"] = now
            return mkts
        return []
    except Exception as e:
        st.warning(f"Could not load Kalshi markets: {e}")
        return []

def run_sentiment(backend: str, query: str, max_results: int = 10):
    return _get(f"{backend}/api/sentiment", params={"q": query, "max_results": max_results})

def place_live_order(backend: str, ticker: str, side: str, price: int, count: int):
    payload = {"ticker": ticker, "side": side.lower(), "price": int(price), "count": int(count)}
    return _post(f"{backend}/api/kalshi/order", json=payload)

def sentiment_recommendation(avg: float, pos: int, neg: int):
    """Toy rule for demo trading."""
    if avg >= 0.15 and pos >= 2 * max(1, neg):
        return ("YES", min(0.99, round(avg, 3)), 60)
    if avg <= -0.15 and neg >= 2 * max(1, pos):
        return ("NO", min(0.99, round(abs(avg), 3)), 60)
    return ("HOLD", 0.3, 50)

# ---- Visualization helpers ----
def gauge_for_signal(side: str, confidence: float) -> go.Figure:
    """
    Plotly gauge showing signal & confidence.
    YES -> green scale, NO -> red scale, HOLD -> gray.
    """
    pct = int(confidence * 100)
    if side == "YES":
        bar_color = "#16a34a"
        steps = [
            {"range": [0, 40], "color": "#dcfce7"},
            {"range": [40, 70], "color": "#bbf7d0"},
            {"range": [70, 100], "color": "#86efac"},
        ]
        title = f"Signal: YES ({pct}%)"
    elif side == "NO":
        bar_color = "#dc2626"
        steps = [
            {"range": [0, 40], "color": "#fee2e2"},
            {"range": [40, 70], "color": "#fecaca"},
            {"range": [70, 100], "color": "#fca5a5"},
        ]
        title = f"Signal: NO ({pct}%)"
    else:
        bar_color = "#6b7280"
        steps = [
            {"range": [0, 100], "color": "#e5e7eb"},
        ]
        title = f"Signal: HOLD"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={'suffix': '%'},
        title={'text': title},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': bar_color},
            'steps': steps,
        }
    ))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=50, b=10))
    return fig

def tiny_stack_counts(pos: int, neg: int, neu: int) -> go.Figure:
    total = max(1, pos + neg + neu)
    df = pd.DataFrame({
        "label": ["Positive", "Neutral", "Negative"],
        "value": [pos/total, neu/total, neg/total]
    })
    fig = go.Figure()
    start = 0
    colors = ["#22c55e", "#6366f1", "#ef4444"]
    for i, row in df.iterrows():
        fig.add_trace(go.Bar(
            x=[row["value"]],
            y=["Sentiment mix"],
            orientation='h',
            name=row["label"],
            marker=dict(color=colors[i]),
            showlegend=True
        ))
    fig.update_layout(barmode='stack', height=120, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_yaxes(visible=False, showticklabels=False)
    fig.update_xaxes(visible=False, showticklabels=False, range=[0,1])
    return fig

# ------------------- Tabs -------------------
st.title("xSent — X → Sentiment → Kalshi Signals")
tabs = st.tabs(["🔎 Analyze", "📈 Markets & Trade", "ℹ️ About"])

# ---------- Analyze tab ----------
with tabs[0]:
    st.subheader("Analyze X sentiment")

    qcol, mcol = st.columns([3, 1])
    with qcol:
        query = st.text_input(
            "Topic or query",
            value=st.session_state["last_query"],
            placeholder="e.g., 'bitcoin', 'Powell press conference', 'CPI'"
        )
    with mcol:
        max_results = st.number_input("Max tweets", min_value=1, max_value=100, value=10)

    if st.button("Analyze Sentiment", type="primary"):
        try:
            result = run_sentiment(BACKEND, query, max_results)
            st.session_state["last_query"] = query
            st.session_state["last_data"] = result
            st.success("Analysis complete.")
        except requests.HTTPError as e:
            st.error(f"Backend error: {e.response.text[:400]}")
        except Exception as e:
            st.error(f"Error: {e}")

    data = st.session_state.get("last_data")
    if data:
        avg = float(data.get("avg_score", 0.0))
        counts = data.get("counts", {})
        pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)

        st.markdown(
            f"**Avg Sentiment:** {avg:+.3f} &nbsp; "
            f"<span class='badge badge-pos'>👍 {pos}</span> "
            f"<span class='badge badge-neg'>👎 {neg}</span> "
            f"<span class='badge badge-neu'>😐 {neu}</span>",
            unsafe_allow_html=True
        )

        items = data.get("items", [])
        if items:
            df = pd.DataFrame([{
                "tweet_id": x.get("id"),
                "score": x.get("score"),
                "label": x.get("label"),
                "text": x.get("text", "")[:180] + ("…" if len(x.get("text","")) > 180 else "")
            } for x in items])

            st.dataframe(df, use_container_width=True, hide_index=True)

            fig = px.histogram(df, x="score", nbins=20, title="Sentiment Score Distribution")
            st.plotly_chart(fig, use_container_width=True)

# ---------- Markets & Trade tab ----------
with tabs[1]:
    left, right = st.columns([3, 2])

    # ---- Left: pick market
    with left:
        st.subheader("Browse Kalshi Markets")

        mkts = fetch_markets_cached(BACKEND, ttl_sec=15)
        if mkts:
            options = []
            for m in mkts:
                lbl = m.get("title") or m.get("name") or m.get("ticker") or "untitled"
                tkr = m.get("ticker")
                if tkr:
                    options.append((lbl, tkr))

            labels = [o[0] for o in options]
            label_to_ticker = {o[0]: o[1] for o in options}

            default_index = labels.index(st.session_state["selected_market_label"]) \
                if st.session_state["selected_market_label"] in label_to_ticker else 0

            choice = st.selectbox("Select a market", labels, index=default_index if labels else 0, key="market_select")
            chosen_ticker = label_to_ticker.get(choice)

            st.session_state["selected_market_label"] = choice
            st.session_state["selected_market_ticker"] = chosen_ticker
            st.caption(f"Ticker: `{chosen_ticker}`")
        else:
            st.warning("No markets available from backend. Check connectivity / keys.")

    # ---- Right: signal + order
    with right:
        st.subheader("Signal & Order")

        data = st.session_state.get("last_data")
        chosen_ticker = st.session_state.get("selected_market_ticker")
        choice_label = st.session_state.get("selected_market_label")

        if not data:
            st.info("Run an analysis in the **Analyze** tab to generate a signal.")
        elif not chosen_ticker:
            st.info("Pick a Kalshi market on the left to link your signal.")
        else:
            avg = float(data.get("avg_score", 0.0))
            counts = data.get("counts", {})
            pos, neg, neu = counts.get("pos", 0), counts.get("neg", 0), counts.get("neu", 0)
            side, conf, price_hint = sentiment_recommendation(avg, pos, neg)

            badge_cls = "sig-yes" if side == "YES" else ("sig-no" if side == "NO" else "sig-hold")
            st.markdown(
                f"**Selected market:** {choice_label}  \n"
                f"**Avg:** {avg:+.3f} — "
                f"<span class='badge {badge_cls}'>Recommendation: {side}</span> "
                f"<span class='small'>(confidence {int(conf*100)}%)</span>",
                unsafe_allow_html=True
            )

            # --- Visuals: gauge + tiny stacked bar
            g1, g2 = st.columns([1, 1])
            with g1:
                st.plotly_chart(gauge_for_signal(side, conf), use_container_width=True)
            with g2:
                st.plotly_chart(tiny_stack_counts(pos, neg, neu), use_container_width=True)

            if side == "HOLD":
                st.info("Signal too weak — hold for now or collect more tweets.")
            else:
                st.divider()
                st.write("### Place Trade")

                with st.form("trade_form"):
                    order_side = st.selectbox("Side", ["YES", "NO"], index=0 if side == "YES" else 1)
                    col1, col2 = st.columns(2)
                    with col1:
                        price = st.slider("Limit price (¢)", 1, 99, price_hint)
                    with col2:
                        qty = st.number_input("Quantity (contracts)", 1, 100, 1)
                    confirm = st.checkbox("I understand this may place a real order.", value=False)
                    submitted = st.form_submit_button("🚀 Execute Trade", type="primary")

                    if submitted:
                        if not confirm:
                            st.warning("Please confirm before executing a real trade.")
                        else:
                            try:
                                side_map = {"YES": "buy", "NO": "sell"}
                                resp = place_live_order(BACKEND, chosen_ticker, side_map[order_side], int(price), int(qty))
                                st.success(f"✅ Order accepted: {resp}")
                            except requests.HTTPError as e:
                                st.error(f"❌ Kalshi API error:\n{e.response.text[:400]}")
                            except Exception as e:
                                st.error(f"Trade failed: {e}")

            with st.expander("See raw sentiment used for this decision"):
                st.json({"avg_score": avg, "counts": counts})

# ---------- About tab ----------
with tabs[2]:
    st.markdown("""
**xSent** turns **X** (Twitter) sentiment into simple **Kalshi** trading signals.

**Flow**
1. Pick a Kalshi market in **Markets & Trade**.
2. Run a query in **Analyze** (e.g., “Powell press conference”, “bitcoin”, “CPI”).
3. We score the latest posts with xAI, aggregate, then apply a toy rule → **YES/NO/HOLD**.
4. If the signal is strong, place a limit order right from the app.

> Auto-Sync refreshes the UI every 5 seconds so the markets list and signal panel stay current without manual clicks.
""")
