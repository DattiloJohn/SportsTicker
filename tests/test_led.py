import re

import pytest

from src.led import (FONT_5x7, GLYPH_WIDTH, MIN_STRIP_WIDTH_PX, build_ticker,
                     normalize_text, text_to_columns)


def test_font_glyphs_are_5x7_bitmaps():
    for ch, glyph in FONT_5x7.items():
        assert len(glyph) == 7, ch
        assert all(re.fullmatch(r"[01]{5}", row) for row in glyph), ch


def test_font_covers_everything_the_ticker_prints():
    needed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -:.|@")
    assert needed <= set(FONT_5x7)


def test_columns_for_single_letter():
    cols = text_to_columns("I", char_spacing=0)
    assert len(cols) == GLYPH_WIDTH
    # "I" row 0 is 01110, so the column bits read left to right across rows
    assert cols[0][0] == "0" and cols[1][0] == "1" and cols[2][0] == "1"
    assert all(len(c) == 7 for c in cols)


def test_spacing_adds_blank_columns():
    base = text_to_columns("AB", char_spacing=0)
    spaced = text_to_columns("AB", char_spacing=2)
    assert len(spaced) == len(base) + 4
    assert spaced[GLYPH_WIDTH:GLYPH_WIDTH + 2] == ["0000000"] * 2


def test_word_spacing_only_applies_to_spaces():
    assert len(text_to_columns(" ", char_spacing=3, word_spacing=0)) == GLYPH_WIDTH
    assert len(text_to_columns(" ", char_spacing=3, word_spacing=2)) == GLYPH_WIDTH + 2


def test_unknown_characters_become_blank_space():
    cols = text_to_columns("~", char_spacing=0)
    assert cols == ["0000000"] * GLYPH_WIDTH


def test_lowercase_and_symbols_are_normalized():
    assert normalize_text("a — b • c") == "A - B | C"
    assert text_to_columns("abc") == text_to_columns("ABC")


def lit_dot_count(html: str) -> int:
    path = re.search(r'<path id="lit-dots" d="([^"]*)"', html).group(1)
    return path.count("M")


def test_lit_dot_count_matches_font_bits():
    html = build_ticker(["T3: NYY 2 @ TB 0"], item_gap="")
    cols = text_to_columns("T3: NYY 2 @ TB 0")
    assert lit_dot_count(html) == sum(c.count("1") for c in cols)


def scroll_distance(html: str) -> float:
    return float(re.search(r"translateX\(-([\d.]+)px\)", html).group(1))


def test_loop_is_seamless_one_copy_width():
    html = build_ticker(["T3: NYY 2 @ TB 0", "F: PIT 7 @ WSH 1"])
    distance = scroll_distance(html)
    xs = [float(x) for x in re.findall(r'<use href="#copy" x="([\d.]+)"', html)]
    assert xs[0] == 0
    assert xs[1] == pytest.approx(distance)       # copy 2 starts where copy 1 ends
    step = xs[1] - xs[0]
    assert all(b - a == pytest.approx(step) for a, b in zip(xs, xs[1:]))


def test_short_text_is_repeated_to_fill_wide_screens():
    html = build_ticker(["HI"])
    xs = re.findall(r'<use href="#copy"', html)
    width = float(re.search(r'<svg[^>]* width="([\d.]+)"', html).group(1))
    assert len(xs) >= 2
    assert width >= MIN_STRIP_WIDTH_PX


def test_page_weight_does_not_grow_per_dot():
    html = build_ticker(["T3: NYY 2 @ TB 0"] * 15)
    assert html.count("<circle") == 1             # unlit dots come from one pattern
    assert "<filter" not in html                  # glow is a stroke, not a filter
    assert html.count("<path") == 1
    assert len(html) < 200_000


def test_empty_items_show_placeholder():
    assert lit_dot_count(build_ticker([])) > 0
