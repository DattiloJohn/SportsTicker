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

    Returns:
        {
            "away_score": str,
            "home_score": str,
            "inning_abbrev": str,   # e.g. "T3", "B7"
            "state_text": str,
            "outs": str,
            "has_linescore": bool
        }
    """
    ld = live_json.get("liveData", {}) or {}
    linescore = ld.get("linescore", {}) or {}
    teams = linescore.get("teams", {}) or {}

    away_score = teams.get("away", {}).get("runs")
    home_score = teams.get("home", {}).get("runs")

    raw_inning = (
        linescore.get("currentInningOrdinal")
        or linescore.get("currentInning")
        or ld.get("plays", {}).get("currentPlay", {}).get("about", {}).get("inning")
    )

    inning_ordinal = "".join(ch for ch in str(raw_inning) if ch.isdigit()) if raw_inning else ""

    half = (
        ld.get("plays", {}).get("currentPlay", {}).get("about", {}).get("halfInning")
        or linescore.get("inningState")
        or ""
    ).lower()

    if inning_ordinal:
        if half.startswith("top"):
            inning_abbrev = f"T{inning_ordinal}"
        elif half.startswith("bottom"):
            inning_abbrev = f"B{inning_ordinal}"
        else:
            inning_abbrev = f"I{inning_ordinal}"
    else:
        inning_abbrev = ""

    outs = linescore.get("outs")
    if outs is None:
        outs = ld.get("plays", {}).get("currentPlay", {}).get("about", {}).get("outs")

    return {
        "away_score": str(away_score or ""),
        "home_score": str(home_score or ""),
        "inning_abbrev": inning_abbrev,
        "state_text": live_json.get("gameData", {}).get("status", {}).get("detailedState", ""),
        "outs": str(outs or ""),
        "has_linescore": bool(linescore)
    }

# -------------------------------------------------
# Game formatting
# -------------------------------------------------

def format_game_item(g: dict) -> str:
    """
    Formats a single MLB game into a compact scoreboard string.

    Examples:
        "NYY 2@TB 0 — T3 O1"
        "LAD @ SF • Scheduled 4:40PM"
    """
    pk = g.get("gamePk")
    away_team = g["teams"]["away"]["team"]
    home_team = g["teams"]["home"]["team"]

    def team_abbr(team_obj: dict) -> str:
        """Returns the best available team abbreviation."""
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

    live = None
    for attempt in range(RETRY_IF_NO_LINESCORE + 1):
        live, _ = fetch_game_live(pk)
        if live and live.get("liveData", {}).get("linescore"):
            break
        time.sleep(RETRY_DELAY)

    if live:
        parsed = extract_score_and_inning(live)

        if parsed["away_score"] or parsed["home_score"] or parsed["inning_abbrev"]:
            score_part = f"{away_abbr} {parsed['away_score']} @ {home_abbr} {parsed['home_score']}"
            extra = parsed["inning_abbrev"] or parsed["state_text"] or detailed or abstract


            return escape(f"{score_part} — {extra}")

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

    text = "•".join(items) if items else "No games found"

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
        "•": ["00000","00000","00100","00000","00100","00000","00000"],
        "@": ["01110","10001","10111","10101","10111","10000","01110"],
    }

    chars = [ch.upper() if ch.upper() in FONT_5x7 else " " for ch in text]

    char_width = 5
    gap_cols = 0
    columns = []

    for ch in chars:
        pattern = FONT_5x7.get(ch, FONT_5x7[" "])
        for col_idx in range(char_width):
            col_bits = "".join(
                pattern[row][col_idx] if col_idx < len(pattern[row]) else "0"
                for row in range(rows)
            )
            columns.append(col_bits)

    total_cols = len(columns)
    dot_total = dot_diameter + dot_spacing
    svg_width = total_cols * dot_total
    svg_height = height_px

    scroll_distance = max(0, svg_width - 1000)
    if scroll_distance <= 0:
        duration = 6.0
    else:
        duration = max(1.5, scroll_distance / speed_px_per_s)

    circles = []
    for c_idx, col in enumerate(columns):
        x = c_idx * dot_total + dot_diameter / 2
        for r_idx in range(rows):
            y = r_idx * dot_total + dot_diameter / 2 + (svg_height - rows * dot_total) / 2
            bit = col[r_idx]
            fill = color if bit == "1" else "#111"
            circles.append(
                f'<circle cx="{x}" cy="{y}" r="{dot_diameter/2}" fill="{fill}" />'
            )

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
