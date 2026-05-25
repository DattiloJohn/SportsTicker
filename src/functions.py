import requests
import time
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

# -------------------------------------------------
# Shared constants (moved here so functions work)
# -------------------------------------------------
API_BASE = "https://statsapi.mlb.com"
TZ_DISPLAY = ZoneInfo("America/New_York")

# Retry settings for live feed
RETRY_IF_NO_LINESCORE = 2
RETRY_DELAY = 0.5

# Ticker visual constants
TICKER_HEIGHT_PX = 200
TICKER_PADDING_PX = 6
TICKER_RENDER_BUFFER = 8

DEFAULT_DOT_DIAMETER = 8
DEFAULT_DOT_SPACING = 3
DEFAULT_ROWS = 7
DEFAULT_COLOR = "#0bff6b"
DEFAULT_BG = "#05060a"
DEFAULT_SPEED_PX_PER_S = 200



# Team name → abbreviation
TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH"
}

# -------------------------------------------------
# Time helpers
# -------------------------------------------------

def now_est_str() -> str:
    """
    Returns the current time in US Eastern Time as a formatted string.
    Used for the "Last updated" display.
    """
    return datetime.now(tz=ZoneInfo("UTC")).astimezone(TZ_DISPLAY).strftime(
        "%Y-%m-%d %I:%M:%S %p %Z"
    )


def to_est_str(iso_ts: str) -> str:
    """
    Converts an ISO timestamp from the MLB API into a simplified EST/EDT time string.

    Example:
        Input:  "2026-05-25T20:40:00Z"
        Output: "4:40PM"
    """
    if not iso_ts:
        return ""

    try:
        if iso_ts.endswith("Z"):
            dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_ts)

        return dt.astimezone(TZ_DISPLAY).strftime("%-I:%M%p")
    except Exception:
        return iso_ts

# -------------------------------------------------
# MLB API fetchers
# -------------------------------------------------

def fetch_todays_games() -> list[dict]:
    """
    Fetches all MLB games scheduled for today's date.

    Returns:
        A list of game dictionaries from the MLB Stats API.
    """
    today = date.today().isoformat()
    url = f"{API_BASE}/api/v1/schedule/games/?sportId=1&date={today}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()
    games = data.get("dates", [])

    return games[0].get("games", []) if games else []


def fetch_game_live(gamePk: int) -> tuple[dict | None, dict]:
    """
    Fetches the live game feed for a given MLB gamePk.

    Returns:
        (live_json, debug_info)
    """
    candidates = [
        f"{API_BASE}/api/v1.1/game/{gamePk}/feed/live",
        f"{API_BASE}/api/v1/game/{gamePk}/feed/live"
    ]

    last_debug = {}

    for url in candidates:
        try:
            r = requests.get(url, timeout=10)
        except Exception as e:
            last_debug = {"url": url, "error": str(e)}
            continue

        if r.status_code != 200:
            last_debug = {"url": url, "status_code": r.status_code}
            continue

        try:
            return r.json(), {"url": url, "status_code": r.status_code}
        except ValueError:
            last_debug = {"url": url, "status_code": r.status_code}

    return None, last_debug

# -------------------------------------------------
# Score + inning extraction
# -------------------------------------------------
def extract_score_and_inning(live_json: dict) -> dict[str, str]:
    """
    Extracts scoreboard information from the MLB live game feed.

    Guarantees:
      - inning_abbrev is always set and will be 'T{n}' or 'B{n}' when possible
      - scores are returned as strings
      - state_text contains the MLB detailedState for fallbacks
    """
    ld = live_json.get("liveData", {}) or {}
    linescore = ld.get("linescore", {}) or {}
    teams = linescore.get("teams", {}) or {}

    # --- Scores ---
    away_score = teams.get("away", {}).get("runs")
    home_score = teams.get("home", {}).get("runs")

    away_score_str = "0" if away_score is None else str(away_score)
    home_score_str = "0" if home_score is None else str(home_score)

    # --- Inning number and state ---
    inning_num = linescore.get("currentInning")
    inning_state = (linescore.get("inningState") or "").lower()

    # --- Outs (kept for completeness; formatter can ignore) ---
    outs = linescore.get("outs")
    outs_str = "" if outs is None else str(outs)

    # Determine inning abbreviation (force to T# or B#)
    # Prefer the explicit inning number from linescore; fall back to parsing any provided abbrev
    if inning_num is None:
        # try to parse digits from any available fields
        raw_abbrev = linescore.get("inningOrdinal") or linescore.get("currentInningOrdinal") or ""
        digits = "".join(ch for ch in str(raw_abbrev) if ch.isdigit())
        inning_num = int(digits) if digits else None

    # final fallback to 1 if nothing available
    if not inning_num:
        inning_num = 1

    # Decide top/bottom
    if inning_state.startswith("top"):
        inning_abbrev = f"T{inning_num}"
    elif inning_state.startswith("bottom"):
        inning_abbrev = f"B{inning_num}"
    else:
        # If MLB doesn't provide a clear top/bottom (e.g., "Middle", "End", or empty),
        # try to inspect plays.currentPlay.about.halfInning if present, otherwise default to Top.
        half = (
            ld.get("plays", {})
            .get("currentPlay", {})
            .get("about", {})
            .get("halfInning", "")
        )
        half = (half or "").lower()
        if half.startswith("bottom"):
            inning_abbrev = f"B{inning_num}"
        elif half.startswith("top"):
            inning_abbrev = f"T{inning_num}"
        else:
            # conservative default
            inning_abbrev = f"T{inning_num}"

    # --- Game state text ---
    state_text = (
        live_json.get("gameData", {})
        .get("status", {})
        .get("detailedState", "")
    )

    return {
        "away_score": away_score_str,
        "home_score": home_score_str,
        "inning_abbrev": inning_abbrev,
        "state_text": state_text,
        "outs": outs_str,
        "has_linescore": bool(linescore)
    }


# -------------------------------------------------
# Game formatting
# -------------------------------------------------
def format_game_item(g: dict) -> str:
    """
    Formats a single MLB game into a compact scoreboard string.

    New format example:
        "T3: NYY 2 @ TB 0"

    Guarantees:
      - inning is always shown as T# or B#
      - outs are not displayed
      - pregame/fallback uses the detailed/abstract state and start time
    """
    pk = g.get("gamePk")
    away_team = g["teams"]["away"]["team"]
    home_team = g["teams"]["home"]["team"]

    def team_abbr(team_obj: dict) -> str:
        return (
            team_obj.get("abbreviation")
            or team_obj.get("triCode")
            or TEAM_ABBR.get(team_obj.get("name", ""), team_obj.get("shortName", team_obj.get("name", "")))
        )

    away_abbr = team_abbr(away_team)
    home_abbr = team_abbr(home_team)

    start_est = to_est_str(g.get("gameDate", ""))
    status = g.get("status", {})
    detailed = status.get("detailedState", "")
    abstract = status.get("abstractGameState", "")

    # Try to fetch live data with retry
    live = None
    for attempt in range(RETRY_IF_NO_LINESCORE + 1):
        live, _ = fetch_game_live(pk)
        if live and live.get("liveData", {}).get("linescore"):
            break
        time.sleep(RETRY_DELAY)

    if live:
        parsed = extract_score_and_inning(live)

        score_part = f"{away_abbr} {parsed['away_score']} @ {home_abbr} {parsed['home_score']}"

        # Determine inning number and half (T/B) robustly
        ls = live.get("liveData", {}).get("linescore", {}) or {}
        inning_state = (ls.get("inningState") or "").lower()
        inning_num = ls.get("currentInning")

        # Fallback: try to parse digits from parsed['inning_abbrev'] or linescore ordinals
        if not inning_num:
            raw_abbrev = parsed.get("inning_abbrev", "") or ls.get("inningOrdinal") or ls.get("currentInningOrdinal") or ""
            digits = "".join(ch for ch in str(raw_abbrev) if ch.isdigit())
            inning_num = int(digits) if digits else None

        # Final fallback to 1
        if not inning_num:
            inning_num = 1

        # Decide top/bottom
        if inning_state.startswith("top"):
            inning = f"T{inning_num}"
        elif inning_state.startswith("bottom"):
            inning = f"B{inning_num}"
        else:
            # Try plays.currentPlay.about.halfInning if inningState is ambiguous
            half = (
                live.get("liveData", {})
                .get("plays", {})
                .get("currentPlay", {})
                .get("about", {})
                .get("halfInning", "") or ""
            )
            half = half.lower()
            if half.startswith("bottom"):
                inning = f"B{inning_num}"
            elif half.startswith("top"):
                inning = f"T{inning_num}"
            else:
                # conservative default
                inning = f"T{inning_num}"

        # New requested format: "T3: NYY 2 @ TB 0"
        return escape(f"{inning}: {score_part}")

    # Pregame / fallback
    return escape(f"{away_abbr} @ {home_abbr} • {detailed or abstract} {start_est}")




def build_ticker(
    items: list[str],
    height_px: int = TICKER_HEIGHT_PX,
    dot_diameter: int = DEFAULT_DOT_DIAMETER,
    dot_spacing: int = DEFAULT_DOT_SPACING,
    rows: int = DEFAULT_ROWS,
    color: str = DEFAULT_COLOR,
    bg: str = DEFAULT_BG,
    padding_px: int = TICKER_PADDING_PX,
    speed_px_per_s: int = DEFAULT_SPEED_PX_PER_S,
    force_loop_for_short_text: bool = False
) -> str:
    """
    Builds the full SVG-based LED ticker display.
    """

    # ORIGINAL TEXT
    text = "•".join(items) if items else "No games found"

    # LED-SAFE NORMALIZATION (NO inning transformations)
    text = (
        text.replace("—", "-")        # em dash → hyphen
            .replace("•", "|")        # bullet → pipe
            .replace("Scheduled", "SCH")
            .replace("Pre-Game", "PRE")
    )

    print("TICKER RAW TEXT:", text)

    FONT_5x7 = {
        "A": ["01110","10001","10001","11111","10001","10001","10001"],
        "B": ["11110","10001","10001","11110","10001","10001","11110"],
        "C": ["01110","10001","10000","10000","10000","10001","01110"],
        "D": ["11110","10001","10001","10001","10001","10001","11110"],
        "E": ["11111","10000","10000","11110","10000","10000","11111"],
        "F": ["11111","10000","10000","11110","10000","10000","10000"],
        "G": ["01110","10001","10000","10111","10001","10001","01110"],
        "H": ["10001","10001","10001","11111","10001","10001","10001"],
        "I": ["01110","00100","00100","00100","00100","00100","01110"],
        "J": ["00111","00010","00010","00010","10010","10010","01100"],
        "K": ["10001","10010","10100","11000","10100","10010","10001"],
        "L": ["10000","10000","10000","10000","10000","10000","11111"],
        "M": ["10001","11011","10101","10101","10001","10001","10001"],
        "N": ["10001","10001","11001","10101","10011","10001","10001"],
        "O": ["01110","10001","10001","10001","10001","10001","01110"],
        "P": ["11110","10001","10001","11110","10000","10000","10000"],
        "Q": ["01110","10001","10001","10001","10101","10010","01101"],
        "R": ["11110","10001","10001","11110","10100","10010","10001"],
        "S": ["01111","10000","10000","01110","00001","00001","11110"],
        "T": ["11111","00100","00100","00100","00100","00100","00100"],
        "U": ["10001","10001","10001","10001","10001","10001","01110"],
        "V": ["10001","10001","10001","10001","10001","01010","00100"],
        "W": ["10001","10001","10001","10101","10101","11011","10001"],
        "X": ["10001","10001","01010","00100","01010","10001","10001"],
        "Y": ["10001","10001","01010","00100","00100","00100","00100"],
        "Z": ["11111","00001","00010","00100","01000","10000","11111"],
        "0": ["01110","10001","10011","10101","11001","10001","01110"],
        "1": ["00100","01100","00100","00100","00100","00100","01110"],
        "2": ["01110","10001","00001","00010","00100","01000","11111"],
        "3": ["01110","10001","00001","00110","00001","10001","01110"],
        "4": ["00010","00110","01010","10010","11111","00010","00010"],
        "5": ["11111","10000","10000","11110","00001","10001","01110"],
        "6": ["00110","01000","10000","11110","10001","10001","01110"],
        "7": ["11111","00001","00010","00100","01000","01000","01000"],
        "8": ["01110","10001","10001","01110","10001","10001","01110"],
        "9": ["01110","10001","10001","01111","00001","00010","01100"],
        " ": ["00000"]*7,
        "-": ["00000","00000","00000","11111","00000","00000","00000"],
        ":": ["00000","00100","00100","00000","00100","00100","00000"],
        ".": ["00000","00000","00000","00000","00000","00110","00110"],
        "|": ["00100","00100","00100","00100","00100","00100","00100"],
        "@": ["01110","10001","10111","10101","10111","10000","01110"],
    }

    # Convert characters to LED glyphs
    chars = [ch.upper() if ch.upper() in FONT_5x7 else " " for ch in text]

    char_width = 5
    dot_total = dot_diameter + dot_spacing
    columns = []

    for ch in chars:
        pattern = FONT_5x7.get(ch, FONT_5x7[" "])
        for col_idx in range(char_width):
            col_bits = "".join(pattern[row][col_idx] for row in range(rows))
            columns.append(col_bits)

    total_cols = len(columns)
    svg_width = total_cols * dot_total
    svg_height = height_px

    scroll_distance = max(0, svg_width - 1000)
    duration = 6.0 if scroll_distance <= 0 else max(1.5, scroll_distance / speed_px_per_s)

    circles = []
    for c_idx, col in enumerate(columns):
        x = c_idx * dot_total + dot_diameter / 2
        for r_idx in range(rows):
            y = r_idx * dot_total + dot_diameter / 2 + (svg_height - rows * dot_total) / 2
            fill = color if col[r_idx] == "1" else "#111"
            circles.append(f'<circle cx="{x}" cy="{y}" r="{dot_diameter/2}" fill="{fill}" />')

    svg = f"""
    <div style="width:100%; background:{bg}; padding:{padding_px}px; border-radius:8px; overflow:hidden;">
      <svg xmlns="http://www.w3.org/2000/svg"
           width="100%" height="{svg_height}"
           viewBox="0 0 {svg_width} {svg_height}"
           preserveAspectRatio="xMinYMid slice">

        <g id="marquee">
          {''.join(circles)}
        </g>

        <style>
          @keyframes marquee-scroll {{
            0% {{ transform: translateX(0px); }}
            100% {{ transform: translateX(-{scroll_distance}px); }}
          }}
          #marquee {{
            animation: marquee-scroll {duration}s linear infinite;
          }}
        </style>
      </svg>
    </div>
    """

    return svg
