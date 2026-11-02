from src import espn_api
from tests.test_mlb_api import FakeResponse


def test_fetch_scoreboard_uses_league_path(monkeypatch, nfl_response):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return FakeResponse(nfl_response)

    monkeypatch.setattr(espn_api.requests, "get", fake_get)
    events = espn_api.fetch_scoreboard("football/nfl")

    assert len(events) == 4
    url, params = calls[0]
    assert url.endswith("/football/nfl/scoreboard")
    assert params == {}                        # NFL: no date, ESPN returns the current week


def test_fetch_scoreboard_formats_date_param(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        espn_api.requests, "get",
        lambda url, params=None, timeout=None: seen.update(params=params) or FakeResponse({"events": []}),
    )
    assert espn_api.fetch_scoreboard("basketball/nba", "2026-11-01") == []
    assert seen["params"] == {"dates": "20261101"}
