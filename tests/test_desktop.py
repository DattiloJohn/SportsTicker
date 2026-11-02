import json
import threading
import time

import pytest

from src import desktop
from src.desktop import (TickerController, UNAVAILABLE, bar_html, host_page,
                         load_settings, save_settings)
from src.leagues import DEFAULT_LEAGUE, LEAGUES


@pytest.fixture
def settings_path(tmp_path):
    return tmp_path / "settings.json"


# ---- settings -------------------------------------------------------------

def test_settings_default_when_file_missing(settings_path):
    assert load_settings(settings_path) == {"league": DEFAULT_LEAGUE}


def test_settings_round_trip(settings_path):
    save_settings({"league": "NFL"}, settings_path)
    assert load_settings(settings_path) == {"league": "NFL"}


@pytest.mark.parametrize("content", ["not json", "[]", '{"league": "NHL"}', '{"league": 5}', ""])
def test_settings_bad_file_falls_back_to_default(settings_path, content):
    settings_path.write_text(content)
    assert load_settings(settings_path) == {"league": DEFAULT_LEAGUE}


def test_save_settings_survives_unwritable_path(tmp_path):
    save_settings({"league": "NBA"}, tmp_path / "missing-dir" / "settings.json")   # no raise


# ---- HTML -----------------------------------------------------------------

def test_host_page_has_every_league_and_quit():
    page = host_page("NFL")
    for name in LEAGUES:
        assert f'data-league="{name}"' in page
    assert "data-quit" in page
    assert '"NFL"' in page                      # current league highlighted on load


def test_host_page_has_set_ticker_and_context_menu_hooks():
    page = host_page()
    assert "function setTicker" in page
    assert "contextmenu" in page and "Escape" in page


def test_bar_html_is_bar_sized():
    html = bar_html(["Q2 9:35 | PHI 10 @ WSH 3"])
    assert f'height="{desktop.BAR_HEIGHT_PX}"' in html
    assert "border-radius:0px" in html


# ---- controller -----------------------------------------------------------

class Recorder:
    def __init__(self):
        self.pushes = []

    def __call__(self, markup):
        self.pushes.append(markup)


def make_controller(settings_path, games, league="MLB"):
    """games: a list of results; each is a list of items or an Exception to raise."""
    save_settings({"league": league}, settings_path)
    results = list(games)
    calls = []

    def load(name):
        calls.append(name)
        result = results.pop(0) if len(results) > 1 else results[0]
        if isinstance(result, Exception):
            raise result
        return result

    push = Recorder()
    return TickerController(push, load, settings_path), push, calls


def test_first_refresh_pushes(settings_path):
    c, push, _ = make_controller(settings_path, [["A @ B | 7PM"]])
    assert c.refresh() is True
    assert len(push.pushes) == 1


def test_unchanged_games_do_not_repush(settings_path):
    c, push, _ = make_controller(settings_path, [["A"], ["A"], ["A"]])
    c.refresh(); c.refresh(); c.refresh()
    assert len(push.pushes) == 1                # scroll is not restarted


def test_changed_games_push_again(settings_path):
    c, push, _ = make_controller(settings_path, [["A 0"], ["A 1"]])
    c.refresh(); c.refresh()
    assert len(push.pushes) == 2


def test_failed_refresh_keeps_last_good_games(settings_path):
    c, push, _ = make_controller(settings_path, [["A"], RuntimeError("offline")])
    c.refresh()
    assert c.refresh() is False
    assert len(push.pushes) == 1


def test_first_refresh_failing_shows_placeholder_once(settings_path):
    c, push, _ = make_controller(settings_path, [RuntimeError("offline")])
    c.refresh(); c.refresh()
    assert len(push.pushes) == 1
    assert push.pushes[0] == bar_html(UNAVAILABLE)


def test_recovery_after_placeholder(settings_path):
    c, push, _ = make_controller(settings_path, [RuntimeError("x"), ["A"]])
    c.refresh(); c.refresh()
    assert push.pushes == [bar_html(UNAVAILABLE), bar_html(["A"])]


def test_set_league_saves_and_wakes(settings_path):
    c, _, _ = make_controller(settings_path, [["A"]])
    c.set_league("NBA")
    assert c.league == "NBA"
    assert load_settings(settings_path)["league"] == "NBA"
    assert c.wake.is_set()


def test_set_league_ignores_unknown(settings_path):
    c, _, _ = make_controller(settings_path, [["A"]])
    c.set_league("NHL")
    assert c.league == "MLB"
    assert not c.wake.is_set()


def test_switch_then_refresh_loads_new_league(settings_path):
    c, push, calls = make_controller(settings_path, [["MLB GAME"], ["NFL GAME"]])
    c.refresh()
    c.set_league("NFL")
    c.refresh()
    assert calls == ["MLB", "NFL"]
    assert push.pushes[-1] == bar_html(["NFL GAME"])


def test_failure_after_switch_never_shows_other_leagues_games(settings_path):
    c, push, _ = make_controller(settings_path, [["MLB GAME"], RuntimeError("offline")])
    c.refresh()
    c.set_league("NFL")
    c.refresh()
    assert push.pushes[-1] == bar_html(UNAVAILABLE)


def test_run_loop_refreshes_and_stops(settings_path):
    c, push, calls = make_controller(settings_path, [["A"]])
    thread = threading.Thread(target=c.run, args=(0.01,))
    thread.start()
    deadline = time.time() + 2
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.005)
    c.stop()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert len(calls) >= 3                      # kept refreshing on the timer
    assert len(push.pushes) == 1                # ...but only pushed once (no change)
