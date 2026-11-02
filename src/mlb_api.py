"""Fetching data from the MLB Stats API."""

import requests

from src.timeutil import sports_date

API_BASE = "https://statsapi.mlb.com"


def fetch_todays_games(date_str: str | None = None) -> list[dict]:
    """
    Fetches all MLB games for a date in a single request.

    The `linescore` and `team` hydrations include scores, inning, and team
    abbreviations, so no per-game calls are needed.
    """
    response = requests.get(
        f"{API_BASE}/api/v1/schedule",
        params={
            "sportId": 1,
            "date": date_str or sports_date(),
            "hydrate": "linescore,team",
        },
        timeout=10,
    )
    response.raise_for_status()

    dates = response.json().get("dates", [])
    return dates[0].get("games", []) if dates else []
