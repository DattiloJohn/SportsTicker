import pytest

from src import leagues
from src.leagues import DEFAULT_LEAGUE, LEAGUES, load_items


def test_the_three_leagues_are_available():
    assert list(LEAGUES) == ["MLB", "NFL", "NBA"]
    assert DEFAULT_LEAGUE in LEAGUES


def test_load_items_formats_each_game(monkeypatch, nba_response):
    monkeypatch.setattr(
        leagues, "LEAGUES",
        {"NBA": leagues.League("NBA", "ESPN", lambda: nba_response["events"], leagues.format_espn_game)},
    )
    items = load_items("NBA")
    assert items[0] == "F: BOS 108 @ ORL 97"
    assert len(items) == 2


def test_unknown_league_raises():
    with pytest.raises(KeyError):
        load_items("NHL")


def test_nba_fetch_is_dated_and_nfl_is_not(monkeypatch):
    calls = []
    monkeypatch.setattr(leagues, "fetch_scoreboard",
                        lambda path, date=None: calls.append((path, date)) or [])
    LEAGUES["NFL"].fetch()
    LEAGUES["NBA"].fetch()
    assert calls[0] == ("football/nfl", None)
    assert calls[1][0] == "basketball/nba" and calls[1][1]
