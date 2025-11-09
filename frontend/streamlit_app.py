# frontend/streamlit_app.py
import os
import requests
import streamlit as st
import plotly.graph_objects as go

# ---- Settings ----
DEFAULT_BACKEND = "http://127.0.0.1:8000"  # change if running elsewhere
BACKEND = os.getenv("XSENT_BACKEND_URL", DEFAULT_BACKEND)

st.set_page_config(page_title="XSent Demo", page_icon="📈", layout="wide")
st.title("📈 XSent – Sentiment → Markets (Demo)")

with st.sidebar:
    st.subheader("Backend")
    BACKEND = st.text_input("Backend URL", BACKEND)
    st.caption("Tip: keep your FastAPI running:  uvicorn backend.app:app --reload")

col1, col2 = st.columns([2, 1], gap="large")

with col1:
    st.subheader("Analyze Topic on X")
    topic = st.text_input("Topic / Query", value="bitcoin")
    max_results = st.slider("Max tweets to analyze", min_value=10, max_value=100, value=30, step=5)
    run_btn = st.button("Analyze Sentiment")

    if run_btn:
        try:
            with st.spinner("Fetching tweets + calling xAI…"):
                r = requests.get(f"{BACKEND}/api/sentiment", params={"q": topic, "max_results": max_results}, timeout=60)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            st.error(f"Error: {e}")
            data = None

        if data:
            st.success("Analysis complete.")
            # Top metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Avg Sentiment", data.get("avg_score", 0.0))
            br = data.get("breakdown", {})
            m2.metric("Positive", br.get("pos", 0))
            m3.metric("Neutral", br.get("neu", 0))
            m4.metric("Negative", br.get("neg", 0))

            # Bar chart breakdown
            fig = go.Figure()
            fig.add_bar(x=["Positive","Neutral","Negative"], y=[br.get("pos",0), br.get("neu",0), br.get("neg",0)])
            fig.update_layout(title=f"Sentiment Breakdown for '{data.get('query','')}'", xaxis_title="", yaxis_title="Count")
            st.plotly_chart(fig, use_container_width=True)

            # Signal badge
            sig = data.get("signal", "NEUTRAL")
            color = {"YES":"green","NO":"red","NEUTRAL":"gray"}[sig]
            st.markdown(f"**Model Signal:** <span style='padding:4px 10px; background:{color}; color:white; border-radius:6px'>{sig}</span>", unsafe_allow_html=True)

            # Sample tweets (no usernames needed)
            st.markdown("#### Sample Tweets")
            for s in data.get("samples", []):
                st.write("• " + s.get("text","")[:300])

with col2:
    st.subheader("Kalshi Markets (Open)")
    if st.button("Refresh Markets"):
        try:
            with st.spinner("Loading Kalshi markets…"):
                r2 = requests.get(f"{BACKEND}/api/kalshi/markets", timeout=60)
                r2.raise_for_status()
                mkts = r2.json()
        except Exception as e:
            st.error(f"Kalshi error: {e}")
            mkts = None

        if mkts:
            # Expecting a list/obj per your Kalshi response; render a compact table if possible
            items = mkts.get("data") if isinstance(mkts, dict) else mkts
            if not items:
                st.info("No markets returned (check credentials or filters).")
            else:
                # show top ~10 markets
                count = 0
                for m in items:
                    count += 1
                    if count > 10: break
                    title = m.get("title") or m.get("ticker") or "Market"
                    status = m.get("status", "—")
                    st.write(f"**{title}**  —  _{status}_")
