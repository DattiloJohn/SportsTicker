"""The leagues the ticker can show, and how to load each one's games as ticker text."""

from dataclasses import dataclass
from typing import Callable

from src.espn_api import fetch_scoreboard
from src.formatting import format_espn_game, format_game_item
from src.mlb_api import fetch_todays_games
from src.timeutil import sports_date


@dataclass(frozen=True)
class League:
    name: str
    source: str                       # shown in the page footer
    fetch: Callable[[], list[dict]]
    format: Callable[[dict], str]


LEAGUES: dict[str, League] = {
    "MLB": League("MLB", "MLB Stats API", fetch_todays_games, format_game_item),
    "NFL": League(
        "NFL", "ESPN",
        lambda: fetch_scoreboard("football/nfl"),          # current week
        format_espn_game,
    ),
    "NBA": League(
        "NBA", "ESPN",
        lambda: fetch_scoreboard("basketball/nba", sports_date()),
        format_espn_game,
    ),
}

DEFAULT_LEAGUE = "MLB"


def load_items(league_name: str) -> list[str]:
    """Fetches a league's games and formats each as one ticker string."""
    league = LEAGUES[league_name]
    return [league.format(game) for game in league.fetch()]
