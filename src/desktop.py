"""
Logic for the desktop ticker bar (no GUI imports, so it can be tested).

DesktopTicker.py wires this to a pywebview window:
  - host_page()        the HTML the window loads once (ticker area + right-click menu)
  - bar_html()         the ticker strip to push into that page
  - TickerController   refreshes games on a timer and pushes changes
  - load/save_settings remembers the chosen league between runs
"""

import html
import json
import threading
from pathlib import Path
from typing import Callable

from src.leagues import DEFAULT_LEAGUE, LEAGUES, load_items
from src.led import build_ticker

REFRESH_SECONDS = 120
BAR_HEIGHT_PX = 56
SETTINGS_PATH = Path.home() / ".sports_ticker.json"
UNAVAILABLE = ["Games unavailable"]


# -------------------------------------------------
# Settings
# -------------------------------------------------

def load_settings(path: Path = SETTINGS_PATH) -> dict:
    """Reads saved settings; a missing, unreadable, or invalid file gives the defaults."""
    settings = {"league": DEFAULT_LEAGUE}
    try:
        saved = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return settings
    if isinstance(saved, dict) and saved.get("league") in LEAGUES:
        settings["league"] = saved["league"]
    return settings


def save_settings(settings: dict, path: Path = SETTINGS_PATH) -> None:
    """Writes settings; failing to save (read-only home, etc.) is not worth crashing for."""
    try:
        Path(path).write_text(json.dumps(settings))
    except OSError:
        pass


# -------------------------------------------------
# HTML
# -------------------------------------------------

def bar_html(items: list[str]) -> str:
    """The ticker strip, sized for a slim bar (smaller dots, no padding or rounded corners)."""
    return build_ticker(
        items,
        height_px=BAR_HEIGHT_PX,
        dot_diameter=5,
        dot_spacing=2,
        padding_px=0,
        border_radius_px=0,
        speed_px_per_s=120,
    )


def host_page(current_league: str = DEFAULT_LEAGUE, leagues: list[str] | None = None) -> str:
    """
    The page the desktop window loads once. The ticker is swapped in later with
    setTicker(html), so the scroll never restarts unless the games change.

    Right-clicking shows a strip over the bar: one button per league, then Quit.
    Buttons call the Python side through window.pywebview.api.
    """
    names = leagues if leagues is not None else list(LEAGUES)
    buttons = "".join(
        f'<button data-league="{html.escape(n)}">{html.escape(n)}</button>' for n in names
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin:0; height:100%; background:#000; overflow:hidden;
               user-select:none; -webkit-user-select:none; cursor:default; }}
  #menu {{ display:none; position:absolute; inset:0; background:rgba(0,0,0,0.88);
          align-items:center; justify-content:center; gap:14px;
          font:600 15px -apple-system, system-ui, sans-serif; }}
  #menu.open {{ display:flex; }}
  #menu button {{ background:#111; color:#0bff6b; border:1px solid #0b6b32; border-radius:6px;
                 padding:6px 18px; font:inherit; cursor:pointer; }}
  #menu button:hover {{ background:#0b3a1e; }}
  #menu button.active {{ background:#0bff6b; color:#000; }}
  #menu .sep {{ width:1px; height:24px; background:#0b6b32; }}
  #menu button.quit {{ color:#ff6b6b; border-color:#6b0b0b; }}
</style>
</head>
<body>
<div id="ticker"></div>
<div id="menu">{buttons}<span class="sep"></span><button class="quit" data-quit="1">Quit</button></div>
<script>
  const menu = document.getElementById("menu");
  function api() {{ return window.pywebview && window.pywebview.api; }}

  function setTicker(markup) {{ document.getElementById("ticker").innerHTML = markup; }}

  function markActive(name) {{
    menu.querySelectorAll("button[data-league]").forEach(b =>
      b.classList.toggle("active", b.dataset.league === name));
  }}
  markActive({json.dumps(current_league)});

  document.addEventListener("contextmenu", e => {{ e.preventDefault(); menu.classList.add("open"); }});
  document.addEventListener("keydown", e => {{ if (e.key === "Escape") menu.classList.remove("open"); }});
  menu.addEventListener("click", e => {{
    const b = e.target.closest("button");
    if (!b) {{ menu.classList.remove("open"); return; }}   // clicked the empty area
    if (b.dataset.quit && api()) api().quit();
    if (b.dataset.league) {{
      markActive(b.dataset.league);
      if (api()) api().set_league(b.dataset.league);
    }}
    menu.classList.remove("open");
  }});
</script>
</body>
</html>"""


# -------------------------------------------------
# Controller
# -------------------------------------------------

class TickerController:
    """
    Keeps the bar up to date.

      load(league) -> list[str]   fetches the league's games as ticker strings
      push(markup)                 puts new ticker HTML on screen

    The bar is only updated when the games actually change (so the scroll doesn't
    jump back to the start on every refresh). If a refresh fails, the last good
    games stay up; if there never were any, "Games unavailable" is shown.
    """

    def __init__(
        self,
        push: Callable[[str], None],
        load: Callable[[str], list[str]] = load_items,
        settings_path: Path = SETTINGS_PATH,
    ):
        self._push = push
        self._load = load
        self._settings_path = settings_path
        self._lock = threading.Lock()
        self._league = load_settings(settings_path)["league"]
        self._last_good: list[str] | None = None    # last successful fetch, this league
        self._shown: list[str] | None = None        # what is on screen now
        self._stop = False
        self.wake = threading.Event()

    @property
    def league(self) -> str:
        return self._league

    def refresh(self) -> bool:
        """Fetches and updates the bar if needed. Returns True if the bar changed."""
        with self._lock:
            try:
                self._last_good = self._load(self._league)
                items = self._last_good
            except Exception:
                items = self._last_good if self._last_good is not None else UNAVAILABLE
            if items == self._shown:
                return False
            self._push(bar_html(items))
            self._shown = items
            return True

    def set_league(self, name: str) -> None:
        """Switches league, remembers it, and wakes the refresh loop to show it now."""
        if name not in LEAGUES:
            return
        with self._lock:
            self._league = name
            self._last_good = None          # never show one league's games under another
        save_settings({"league": name}, self._settings_path)
        self.wake.set()

    def stop(self) -> None:
        self._stop = True
        self.wake.set()

    def run(self, interval: float = REFRESH_SECONDS) -> None:
        """Refreshes now, then every `interval` seconds (or sooner on a league change)."""
        while not self._stop:
            self.refresh()
            self.wake.wait(interval)
            self.wake.clear()
