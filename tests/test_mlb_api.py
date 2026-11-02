from src import mlb_api


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_requests_hydrated_schedule(monkeypatch, schedule_response):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return FakeResponse(schedule_response)

    monkeypatch.setattr(mlb_api.requests, "get", fake_get)
    games = mlb_api.fetch_todays_games("2026-07-04")

    assert len(games) == 2
    assert len(calls) == 1                      # one request, not one per game
    url, params = calls[0]
    assert url.endswith("/api/v1/schedule")
    assert params["date"] == "2026-07-04"
    assert "linescore" in params["hydrate"]


def test_fetch_returns_empty_list_on_off_day(monkeypatch):
    monkeypatch.setattr(
        mlb_api.requests, "get",
        lambda *a, **k: FakeResponse({"dates": []}),
    )
    assert mlb_api.fetch_todays_games("2026-11-01") == []
