import pytest

from src.formatting import format_espn_game, period_label
from tests.conftest import make_espn_event

TODAY = "2026-11-01"


def test_nfl_fixture(nfl_response):
    games = nfl_response["events"]
    assert [format_espn_game(g, today=TODAY) for g in games] == [
        "Q2 8:19 | PHI 10 @ WSH 3",
        "F: BAL 10 @ BUF 36",
        "F/OT: TEN 36 @ CIN 43",
        "CHI @ SEA | MON 8:15PM",          # Monday game gets a day prefix
    ]


def test_nba_fixture(nba_response):
    games = nba_response["events"]
    assert [format_espn_game(g, today=TODAY) for g in games] == [
        "F: BOS 108 @ ORL 97",
        "Q2 5:30 | LAC 41 @ GS 45",
    ]


def test_pregame_today_has_no_day_prefix():
    # 2026-11-02T01:20Z is 8:20PM Eastern on Nov 1
    g = make_espn_event("pre", "STATUS_SCHEDULED", date="2026-11-02T01:20Z")
    assert format_espn_game(g, today=TODAY) == "PHI @ WSH | 8:20PM"


def test_halftime_and_end_of_period():
    half = make_espn_event("in", "STATUS_HALFTIME", period=2)
    end = make_espn_event("in", "STATUS_END_PERIOD", period=1)
    assert format_espn_game(half) == "HALF | PHI 10 @ WSH 3"
    assert format_espn_game(end) == "END Q1 | PHI 10 @ WSH 3"


def test_live_overtime():
    g = make_espn_event("in", "STATUS_IN_PROGRESS", period=5, clock="2:31")
    assert format_espn_game(g) == "OT 2:31 | PHI 10 @ WSH 3"


def test_nba_double_overtime_final():
    g = make_espn_event("post", "STATUS_FINAL", detail="Final/2OT", period=6)
    assert format_espn_game(g) == "F/2OT: PHI 10 @ WSH 3"


def test_postponed_is_not_shown_as_final():
    g = make_espn_event("post", "STATUS_POSTPONED", description="Postponed")
    assert format_espn_game(g) == "PHI @ WSH | Postponed"


def test_delayed_pregame_shows_reason():
    g = make_espn_event("pre", "STATUS_DELAYED", description="Delayed")
    assert format_espn_game(g, today=TODAY) == "PHI @ WSH | Delayed 8:20PM"


def test_missing_scores_default_to_zero():
    g = make_espn_event("in", "STATUS_IN_PROGRESS", clock="15:00")
    for c in g["competitions"][0]["competitors"]:
        del c["score"]
    assert format_espn_game(g) == "Q1 15:00 | PHI 0 @ WSH 0"


@pytest.mark.parametrize("period, label", [
    (1, "Q1"), (4, "Q4"), (5, "OT"), (6, "2OT"), (7, "3OT"),
])
def test_period_label(period, label):
    assert period_label(period) == label
