import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json

from src.functions import (
    now_est_str,
    fetch_todays_games,
    format_game_item,
    build_ticker
)

st.set_page_config(page_title="Live Baseball Ticker", layout="wide")
st.title("Live Baseball Ticker")

REFRESH_SECONDS = 120
TICKER_HEIGHT_PX = 200
TICKER_RENDER_BUFFER = 8

st.session_state.setdefault("refresh_count", 0)
refresh_count = st_autorefresh(interval=REFRESH_SECONDS * 1000, limit=None, key="autorefresh")

try:
    games = fetch_todays_games()
    items = [format_game_item(g) for g in games]
    ticker_html = build_ticker(items, height_px=TICKER_HEIGHT_PX, force_loop_for_short_text=True)
except Exception as e:
    ticker_html = build_ticker([f"Error fetching games: {e}"])

st.components.v1.html(ticker_html, height=TICKER_HEIGHT_PX + TICKER_RENDER_BUFFER)

last_updated_str = now_est_str()

status_html = f"""
<div style="display:flex; align-items:center; gap:12px; margin-top:8px; color:#ffffff;">
  <div style="font-weight:600;">Last updated (EST/EDT):</div>
  <div style="font-weight:600;">{last_updated_str}</div>
  <div style="background:#16a34a; color:#ffffff; padding:4px 8px; border-radius:12px; font-weight:600; margin-left:8px; animation:pulse 1s ease-out;">Updated</div>
  <div style="margin-left:8px; color:#d1d5db;">Refreshes: {refresh_count}</div>
</div>

<style>
@keyframes pulse {{
  0% {{ transform:scale(1.0); opacity:1; }}
  60% {{ transform:scale(1.18); opacity:0.95; }}
  100% {{ transform:scale(1.0); opacity:1; }}
}}
</style>
"""

st.components.v1.html(status_html, height=56)

safe_ts = json.dumps(last_updated_str)
title_js = f"""
<script>ß
try {{
    const originalTitle = document.title;
    const ts = {safe_ts};
    document.title = "⚾ Updated: " + ts;
    setTimeout(() => {{ document.title = originalTitle; }}, 6000);
}} catch(e){{}}
</script>
"""

st.components.v1.html(title_js, height=0)

st.caption(f"Auto-refresh every {REFRESH_SECONDS}s — data from MLB Stats API.")
print("hi")