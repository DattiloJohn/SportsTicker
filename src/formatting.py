"""Turning MLB schedule games into short ticker strings."""

from src.timeutil import sports_date, to_est_dt, to_est_str

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


def team_abbr(side: dict) -> str:
    """Abbreviation for one side ("away"/"home") of a schedule game."""
    team = side.get("team", {})
    name = team.get("name", "")
    return (
        team.get("abbreviation")
        or TEAM_ABBR.get(name)
        or team.get("teamName", name)
    )


def inning_label(linescore: dict) -> str:
    """Returns 'T3' / 'B3', or 'MID3' / 'END3' between half-innings."""
    num = linescore.get("currentInning") or 1
    state = (linescore.get("inningState") or "").lower()
    if state.startswith("mid"):
        return f"MID{num}"
    if state.startswith("end"):
        return f"END{num}"
    if state.startswith("bottom") or linescore.get("isTopInning") is False:
        return f"B{num}"
    return f"T{num}"


def format_game_item(g: dict) -> str:
    """
    Formats one schedule game as a compact ticker string.

        Preview:   "BOS @ NYY | Scheduled 7:05PM"
        Live:      "T3: NYY 2 @ TB 0"
        Final:     "F: PIT 7 @ CHC 1"   ("F10:" after extra innings)
        Postponed: "BOS @ NYY | Postponed"
    """
    away, home = g["teams"]["away"], g["teams"]["home"]
    away_abbr, home_abbr = team_abbr(away), team_abbr(home)

    status = g.get("status", {})
    abstract = status.get("abstractGameState", "")
    detailed = status.get("detailedState", "")
    linescore = g.get("linescore") or {}
    ls_teams = linescore.get("teams", {})

    def runs(side_key: str, side: dict) -> str:
        value = ls_teams.get(side_key, {}).get("runs")
        if value is None:
            value = side.get("score")
        return str(value if value is not None else 0)

    scoreline = f"{away_abbr} {runs('away', away)} @ {home_abbr} {runs('home', home)}"

    if abstract == "Live":
        suffix = f" | {detailed}" if "delay" in detailed.lower() else ""
        return f"{inning_label(linescore)}: {scoreline}{suffix}"

    if abstract == "Final" and detailed.lower().startswith(("final", "game over", "completed")):
        innings = linescore.get("currentInning") or 9
        scheduled = linescore.get("scheduledInnings") or 9
        return f"F{innings if innings != scheduled else ''}: {scoreline}"

    # Preview, postponed, cancelled, suspended, etc.
    start = to_est_str(g.get("gameDate", ""))
    return f"{away_abbr} @ {home_abbr} | {detailed or abstract} {start}".strip()


# -------------------------------------------------
# ESPN (NFL / NBA)
# -------------------------------------------------

# ESPN statuses where the game isn't really on, even if it has a start time
_NOT_PLAYED = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED", "STATUS_FORFEIT"}


def period_label(period: int, regulation: int = 4) -> str:
    """Q1..Q4, then OT, 2OT, ... (NFL and NBA both play four quarters)."""
    if period <= regulation:
        return f"Q{period}"
    overtime = period - regulation
    return "OT" if overtime == 1 else f"{overtime}OT"


def format_espn_game(event: dict, today: str | None = None) -> str:
    """
    Formats one ESPN scoreboard event as a compact ticker string.

        Pregame:   "PHI @ WSH | 8:20PM"   (with a day prefix if not today: "THU 8:20PM")
        Live:      "Q2 9:35 | PHI 10 @ WSH 3"   ("HALF |", "END Q1 |" between periods)
        Final:     "F: BAL 10 @ BUF 36"   ("F/OT:" after overtime)
        Postponed: "PHI @ WSH | Postponed"
    """
    competition = event["competitions"][0]
    sides = {c["homeAway"]: c for c in competition["competitors"]}
    away, home = sides["away"], sides["home"]

    def abbr(side: dict) -> str:
        team = side.get("team", {})
        return team.get("abbreviation") or team.get("shortDisplayName") or team.get("name", "")

    matchup = f"{abbr(away)} @ {abbr(home)}"
    scoreline = f"{abbr(away)} {away.get('score', 0)} @ {abbr(home)} {home.get('score', 0)}"

    status = event.get("status", {})
    status_type = status.get("type", {})
    state = status_type.get("state", "pre")
    name = status_type.get("name", "")
    description = status_type.get("description", "")

    if name in _NOT_PLAYED:
        return f"{matchup} | {description}"

    if state == "in":
        period = period_label(status.get("period") or 1)
        if name == "STATUS_HALFTIME":
            return f"HALF | {scoreline}"
        if name == "STATUS_END_PERIOD":
            return f"END {period} | {scoreline}"
        clock = status.get("displayClock", "")
        suffix = f" | {description}" if name in ("STATUS_DELAYED", "STATUS_RAIN_DELAY") else ""
        return f"{period} {clock}".strip() + f" | {scoreline}{suffix}"

    if state == "post":
        detail = status_type.get("shortDetail", "Final")
        label = "F" + detail[len("Final"):] if detail.startswith("Final") else "F"
        return f"{label}: {scoreline}"

    # Pregame
    start = to_est_dt(event.get("date", ""))
    if start is None:
        return f"{matchup} | {description}".strip(" |")
    when = to_est_str(event["date"])
    if start.date().isoformat() != (today or sports_date()):
        when = f"{start.strftime('%a').upper()} {when}"
    if name not in ("STATUS_SCHEDULED", ""):
        when = f"{description} {when}"
    return f"{matchup} | {when}"
