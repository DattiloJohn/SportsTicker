"""Fetching scoreboards from ESPN's public (unofficial) scoreboard feed."""

import requests

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


def fetch_scoreboard(sport_path: str, date_str: str | None = None) -> list[dict]:
    """
    Fetches the events on a league's scoreboard, e.g. "football/nfl".

    Without a date, ESPN returns its current slate (for the NFL, the current week).
    """
    params = {"dates": date_str.replace("-", "")} if date_str else {}
    response = requests.get(
        f"{ESPN_BASE}/{sport_path}/scoreboard", params=params, timeout=10
    )
    response.raise_for_status()
    return response.json().get("events", [])
