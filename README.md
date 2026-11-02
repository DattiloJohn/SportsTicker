# Live Sports Ticker

A Streamlit app that shows live MLB, NFL or NBA scores as a scrolling LED-dot ticker, like a stock ticker. Pick the league with the buttons above the ticker; it refreshes itself every 2 minutes.

```
T3: NYY 2 @ TB 0     B7: BOS 2 @ ATH 5     F: PIT 7 @ WSH 1     BOS @ NYY | Scheduled 7:05PM
```

**MLB**

| Game state | Display |
|---|---|
| Not started | `AWY @ HOM \| Scheduled 7:05PM` (Eastern time) |
| In progress | `T3: AWY 2 @ HOM 0` (`T` = top, `B` = bottom, `MID`/`END` between halves) |
| Final | `F: AWY 7 @ HOM 1` (`F10:` if it went to extra innings) |
| Postponed, delayed, etc. | The status MLB reports, e.g. `AWY @ HOM \| Postponed` |

**NFL and NBA**

| Game state | Display |
|---|---|
| Not started | `AWY @ HOM \| 8:20PM` (with a day prefix if not today, e.g. `MON 8:15PM`) |
| In progress | `Q2 9:35 \| AWY 10 @ HOM 3` (`OT`, `2OT`, ... in overtime; `HALF \|` and `END Q1 \|` between periods) |
| Final | `F: AWY 10 @ HOM 36` (`F/OT:` after overtime) |
| Postponed, canceled, etc. | `AWY @ HOM \| Postponed` |

The NFL ticker shows the current week's games; MLB and NBA show today's games.

On days with no games the ticker shows `NO GAMES FOUND`.

## Requirements

- Python 3.10 or newer
- An internet connection (data comes from the MLB Stats API and ESPN's public scoreboard feed; no API key needed)

## Setup and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run SportsTicker.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## How it works

1. The chosen league (kept in the URL as `?league=NFL`, so a browser reload keeps it) is loaded by `src/leagues.py`. MLB makes one request to the MLB schedule endpoint; NFL and NBA make one request to ESPN's scoreboard.
2. `format_game_item()` (MLB) or `format_espn_game()` (NFL/NBA) turns each game into a short text string.
3. `build_ticker()` converts the text into a 5x7 dot-matrix font and draws it as SVG: unlit dots are one tiled pattern, lit dots are a single path with a soft halo stroke for the glow, and a CSS animation scrolls the strip.
4. The strip is drawn as repeated copies and scrolls by exactly one copy's width, so the loop is seamless at any screen width.
5. `SportsTicker.py` shows the SVG, a "last updated" line, and flashes the browser tab title on each refresh. Results are cached for 60 seconds.

"Today" uses Eastern time and rolls over at 5 AM, so late West Coast games stay on the ticker after midnight.

## Desktop bar

Prefer it on your desktop instead of a browser tab? `DesktopTicker.py` shows the same ticker as a slim, borderless bar across the top of your screen that stays on top of other windows. It doesn't use Streamlit or a browser.

```bash
pip install -r requirements-desktop.txt
python DesktopTicker.py
```

- **Right-click** the bar for a menu: MLB / NFL / NBA, or Quit. Your league choice is remembered in `~/.sports_ticker.json`.
- **Drag** the bar to move it. It starts at the top of the main screen each time you launch.
- It refreshes every 2 minutes, and only restarts the scroll when the games actually change.
- To start it at login on macOS: System Settings → General → Login Items → add a small script or app that runs `python /path/to/DesktopTicker.py` using the Python where you installed the requirements.

## Configuration

Page settings are constants at the top of `SportsTicker.py`:

| Constant | Default | Meaning |
|---|---|---|
| `REFRESH_SECONDS` | `120` | How often the page reloads data |
| `CACHE_SECONDS` | `60` | How long fetched results are reused |

Look and feel are options on `build_ticker()` in `src/led.py`. The defaults are module constants (`DEFAULT_COLOR`, `DEFAULT_BG`, and so on):

| Option | Default | Meaning |
|---|---|---|
| `color` | `#0bff6b` | Lit dot color |
| `bg` | `#000000` | Background color |
| `dot_diameter`, `dot_spacing` | `8`, `3` | Dot size and gap, in pixels |
| `char_spacing`, `word_spacing` | `1`, `0` | Blank dot columns between characters / after spaces |
| `speed_px_per_s` | `200` | Scroll speed |
| `height_px` | `200` | Ticker height |
| `item_gap` | 4 spaces | Text between games |

The font only has letters, digits, and `- : . | @ / space`. Any other character is shown as a space.

## Project layout

```
SportsTicker.py          Streamlit page (browser version)
DesktopTicker.py         Desktop bar (pywebview window)
src/desktop.py           Desktop bar logic: settings, right-click menu page, refresh loop
src/leagues.py           The MLB / NFL / NBA choices: how each is fetched and formatted
src/mlb_api.py           Fetches the day's games from the MLB Stats API
src/espn_api.py          Fetches NFL / NBA scoreboards from ESPN
src/formatting.py        Turns a game into ticker text (scores, innings/quarters, status)
src/led.py               5x7 font and SVG ticker renderer
src/timeutil.py          Eastern-time helpers and the "which day is it" rule
tests/                   pytest suite; tests/fixtures has a saved schedule response
requirements.txt         Dependencies for the Streamlit version
requirements-desktop.txt Dependencies for the desktop bar
requirements-dev.txt     Streamlit dependencies + pytest
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests run offline. They use saved real responses in `tests/fixtures/` (an MLB schedule of finished games, an ESPN NFL week and an ESPN NBA day) plus small made-up games for the other states (live, pregame, postponed, overtime).

## Notes

- The MLB Stats API and ESPN's scoreboard feed are public but unofficial and undocumented, so their formats can change without notice.
- Team abbreviations come from the APIs; `TEAM_ABBR` in `src/formatting.py` is only an MLB fallback.
- To add another league ESPN covers (e.g. `hockey/nhl`), add one entry to `LEAGUES` in `src/leagues.py`; the NFL/NBA formatter already handles four-period sports.
