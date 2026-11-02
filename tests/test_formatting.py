import pytest

from src.formatting import format_game_item, inning_label, team_abbr
from src.timeutil import sports_date, to_est_str
from tests.conftest import make_game


def runs(away, home):
    return {"teams": {"away": {"runs": away}, "home": {"runs": home}}}


def test_final_games_from_real_response(schedule_response):
    games = schedule_response["dates"][0]["games"]
    assert [format_game_item(g) for g in games] == [
        "F: PIT 7 @ WSH 1",
        "F: MIN 11 @ NYY 4",
    ]


def test_live_top_and_bottom():
    top = make_game("Live", "In Progress",
                    {"currentInning": 3, "inningState": "Top", **runs(2, 0)})
    bottom = make_game("Live", "In Progress",
                       {"currentInning": 7, "inningState": "Bottom", **runs(2, 5)})
    assert format_game_item(top) == "T3: BOS 2 @ NYY 0"
    assert format_game_item(bottom) == "B7: BOS 2 @ NYY 5"


def test_live_between_halves():
    g = make_game("Live", "In Progress", {"currentInning": 5, "inningState": "Middle"})
    assert format_game_item(g) == "MID5: BOS 0 @ NYY 0"


def test_live_delay_is_shown():
    g = make_game("Live", "Delayed: Rain", {"currentInning": 2, "inningState": "Top"})
    assert format_game_item(g) == "T2: BOS 0 @ NYY 0 | Delayed: Rain"


def test_preview_shows_start_time_in_eastern():
    g = make_game("Preview", "Scheduled", date="2026-07-04T23:05:00Z")
    assert format_game_item(g) == "BOS @ NYY | Scheduled 7:05PM"


def test_postponed_is_not_shown_as_final():
    g = make_game("Final", "Postponed")
    assert format_game_item(g).startswith("BOS @ NYY | Postponed")


def test_extra_innings_final():
    g = make_game("Final", "Final",
                  {"currentInning": 10, "scheduledInnings": 9, **runs(4, 3)})
    assert format_game_item(g) == "F10: BOS 4 @ NYY 3"


def test_inning_label_falls_back_to_is_top_inning():
    assert inning_label({"currentInning": 4, "isTopInning": False}) == "B4"
    assert inning_label({}) == "T1"


def test_team_abbr_falls_back_to_name_table():
    assert team_abbr({"team": {"name": "Athletics"}}) == "ATH"


@pytest.mark.parametrize("iso, expected", [
    ("2026-07-04T23:05:00Z", "7:05PM"),
    ("2026-01-15T18:05:00Z", "1:05PM"),   # EST, not EDT
    ("", ""),
    ("not a date", "not a date"),
])
def test_to_est_str(iso, expected):
    assert to_est_str(iso) == expected


def test_sports_date_rolls_over_at_5am_eastern():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    assert sports_date(datetime(2026, 7, 5, 1, 30, tzinfo=et)) == "2026-07-04"
    assert sports_date(datetime(2026, 7, 5, 5, 0, tzinfo=et)) == "2026-07-05"
