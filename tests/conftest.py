import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def schedule_response() -> dict:
    """A real (trimmed) MLB schedule response for 2026-07-04, all games final."""
    return json.loads((FIXTURES / "schedule_2026-07-04.json").read_text())


@pytest.fixture
def nfl_response() -> dict:
    """Real (trimmed) ESPN NFL scoreboard: live, final, final/OT, and a Monday game."""
    return json.loads((FIXTURES / "espn_nfl_week.json").read_text())


@pytest.fixture
def nba_response() -> dict:
    """Real (trimmed) ESPN NBA scoreboard: one final, one live."""
    return json.loads((FIXTURES / "espn_nba_day.json").read_text())


def make_espn_event(state, name, detail="", period=1, clock="", date="2026-11-02T01:20Z",
                    away=("PHI", 10), home=("WSH", 3), description=""):
    """Builds a minimal ESPN event dict for status cases the fixtures lack."""
    return {
        "date": date,
        "status": {
            "period": period,
            "displayClock": clock,
            "type": {"state": state, "name": name, "shortDetail": detail,
                     "description": description},
        },
        "competitions": [{"competitors": [
            {"homeAway": "home", "score": str(home[1]), "team": {"abbreviation": home[0]}},
            {"homeAway": "away", "score": str(away[1]), "team": {"abbreviation": away[0]}},
        ]}],
    }


def make_game(abstract, detailed, linescore=None, away="BOS", home="NYY",
              date="2026-07-04T23:05:00Z"):
    """Builds a minimal schedule game dict for status cases the fixture lacks."""
    return {
        "gameDate": date,
        "status": {"abstractGameState": abstract, "detailedState": detailed},
        "teams": {
            "away": {"team": {"abbreviation": away}},
            "home": {"team": {"abbreviation": home}},
        },
        "linescore": linescore or {},
    }
