import json

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.leagues import DEFAULT_LEAGUE, LEAGUES, load_items
from src.led import TICKER_HEIGHT_PX, TICKER_RENDER_BUFFER, build_ticker
from src.timeutil import now_est_str

REFRESH_SECONDS = 120
CACHE_SECONDS = 60

st.set_page_config(page_title="Live Sports Ticker", layout="wide")
st.title("Live Sports Ticker")

refresh_count = st_autorefresh(interval=REFRESH_SECONDS * 1000, limit=None, key="autorefresh")


# Remember the chosen league in the URL (?league=NFL) so a browser reload keeps it.
league_names = list(LEAGUES)
saved = st.query_params.get("league", DEFAULT_LEAGUE)
league_name = st.radio(
    "League",
    league_names,
    index=league_names.index(saved) if saved in league_names else 0,
    horizontal=True,
    label_visibility="collapsed",
)
st.query_params["league"] = league_name


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def load_league_items(name: str) -> list[str]:
    """Fetch a league's games and format them. Cached so extra tabs/reruns don't refetch."""
    return load_items(name)


last_updated_str = now_est_str()

try:
    items = load_league_items(league_name)
    ticker_html = build_ticker(items, height_px=TICKER_HEIGHT_PX)
except Exception as e:
    st.error(f"Could not load games: {e}")
    ticker_html = build_ticker(["Games unavailable"], height_px=TICKER_HEIGHT_PX)

# The ticker's HTML must not change between refreshes (no timestamps in it),
# otherwise the browser reloads the iframe and the scroll jumps back to the start.
st.iframe(ticker_html.strip(), height=TICKER_HEIGHT_PX + TICKER_RENDER_BUFFER)

st.html(
    f"""
<div style="display:flex; align-items:center; gap:12px; margin-top:8px;">
  <div style="font-weight:600;">Last updated (Eastern):</div>
  <div style="font-weight:600;">{last_updated_str}</div>
  <div style="background:#16a34a; color:#ffffff; padding:4px 8px; border-radius:12px; font-weight:600; animation:pulse 1s ease-out;">Updated</div>
  <div style="opacity:0.7;">Refreshes: {refresh_count}</div>
</div>
<style>
@keyframes pulse {{
  0% {{ transform:scale(1.0); opacity:1; }}
  60% {{ transform:scale(1.18); opacity:0.95; }}
  100% {{ transform:scale(1.0); opacity:1; }}
}}
</style>
<script>
// Briefly flash the browser tab title on each refresh.
try {{
    const originalTitle = document.title;
    document.title = "🏟️ Updated: " + {json.dumps(last_updated_str)};
    setTimeout(() => {{ document.title = originalTitle; }}, 6000);
}} catch (e) {{}}
</script>
""",
    unsafe_allow_javascript=True,
)

st.caption(f"Auto-refresh every {REFRESH_SECONDS}s — data from {LEAGUES[league_name].source}.")
