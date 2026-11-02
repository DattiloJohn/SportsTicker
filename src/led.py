"""LED dot-matrix ticker: 5x7 font and SVG renderer."""

import math

# Ticker visual defaults
TICKER_HEIGHT_PX = 200
TICKER_PADDING_PX = 6
TICKER_RENDER_BUFFER = 8

DEFAULT_DOT_DIAMETER = 8
DEFAULT_DOT_SPACING = 3
DEFAULT_ROWS = 7
DEFAULT_COLOR = "#0bff6b"
DEFAULT_BG = "#000000"
DEFAULT_UNLIT = "#111111"
DEFAULT_SPEED_PX_PER_S = 200

# The strip is repeated until it is at least this wide, so the second copy
# always fills the screen while the first scrolls out (even on wide monitors).
MIN_STRIP_WIDTH_PX = 4000

# Glow around lit dots: a stroke this wide (as a fraction of the dot diameter)
# at this opacity, drawn on the same path as the dots.
GLOW_WIDTH_RATIO = 0.6
GLOW_OPACITY = 0.3

GLYPH_WIDTH = 5

# 5x7 font (only the characters we support); each glyph is 7 rows of 5 bits
FONT_5x7 = {
    "A": ["01110","10001","10001","11111","10001","10001","10001"],
    "B": ["11110","10001","10001","11110","10001","10001","11110"],
    "C": ["01110","10001","10000","10000","10000","10001","01110"],
    "D": ["11110","10001","10001","10001","10001","10001","11110"],
    "E": ["11111","10000","10000","11110","10000","10000","11111"],
    "F": ["11111","10000","10000","11110","10000","10000","10000"],
    "G": ["01110","10001","10000","10111","10001","10001","01110"],
    "H": ["10001","10001","10001","11111","10001","10001","10001"],
    "I": ["01110","00100","00100","00100","00100","00100","01110"],
    "J": ["00111","00010","00010","00010","10010","10010","01100"],
    "K": ["10001","10010","10100","11000","10100","10010","10001"],
    "L": ["10000","10000","10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10101","10001","10001","10001"],
    "N": ["10001","10001","11001","10101","10011","10001","10001"],
    "O": ["01110","10001","10001","10001","10001","10001","01110"],
    "P": ["11110","10001","10001","11110","10000","10000","10000"],
    "Q": ["01110","10001","10001","10001","10101","10010","01101"],
    "R": ["11110","10001","10001","11110","10100","10010","10001"],
    "S": ["01111","10000","10000","01110","00001","00001","11110"],
    "T": ["11111","00100","00100","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10001","10101","10101","11011","10001"],
    "X": ["10001","10001","01010","00100","01010","10001","10001"],
    "Y": ["10001","10001","01010","00100","00100","00100","00100"],
    "Z": ["11111","00001","00010","00100","01000","10000","11111"],
    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"],
    "3": ["01110","10001","00001","00110","00001","10001","01110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","10000","11110","00001","10001","01110"],
    "6": ["00110","01000","10000","11110","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00010","01100"],
    " ": ["00000"]*7,
    "-": ["00000","00000","00000","11111","00000","00000","00000"],
    ":": ["00000","00100","00100","00000","00100","00100","00000"],
    ".": ["00000","00000","00000","00000","00000","00110","00110"],
    "|": ["00100","00100","00100","00100","00100","00100","00100"],
    "/": ["00001","00001","00010","00100","01000","10000","10000"],
    "@": ["01110","10001","10111","10101","10111","10000","01110"],
}


def normalize_text(text: str) -> str:
    """Replaces characters the font lacks with close equivalents, then upper-cases."""
    text = (
        text.replace("\u2014", "-")   # em dash
            .replace("\u2013", "-")   # en dash
            .replace("\u2022", "|")   # bullet
    )
    return text.upper()


def text_to_columns(
    text: str,
    rows: int = DEFAULT_ROWS,
    char_spacing: int = 1,
    word_spacing: int = 0,
) -> list[str]:
    """
    Converts text to LED columns. Each column is a string of `rows` bits
    ("1" = lit), top row first. Characters missing from the font become spaces.
    """
    columns: list[str] = []
    blank = "0" * rows
    for ch in normalize_text(text):
        ch = ch if ch in FONT_5x7 else " "
        glyph = FONT_5x7[ch]
        for col in range(GLYPH_WIDTH):
            columns.append("".join(glyph[row][col] for row in range(rows)))
        gap = word_spacing if ch == " " else char_spacing
        columns.extend([blank] * max(0, gap))
    return columns


def build_ticker(
    items: list[str],
    height_px: int = TICKER_HEIGHT_PX,
    dot_diameter: int = DEFAULT_DOT_DIAMETER,
    dot_spacing: int = DEFAULT_DOT_SPACING,
    char_spacing: int = 1,
    word_spacing: int = 0,
    rows: int = DEFAULT_ROWS,
    color: str = DEFAULT_COLOR,
    bg: str = DEFAULT_BG,
    padding_px: int = TICKER_PADDING_PX,
    speed_px_per_s: int = DEFAULT_SPEED_PX_PER_S,
    item_gap: str = "    ",
    border_radius_px: int = 8,
) -> str:
    """
    Builds the SVG LED ticker as an HTML snippet.

    Rendering is kept cheap:
      - unlit dots are one tiled <pattern> rectangle, not individual circles
      - lit dots are a single <path>; the glow is a translucent stroke on that
        same path (no SVG filter, so the animation stays cheap)
      - the text strip is defined once and repeated with <use>

    The strip scrolls left by exactly one copy's width and then restarts on an
    identical copy, so the loop is seamless at any screen width.
    """
    text = (item_gap.join(items) if items else "No games found") + item_gap
    columns = text_to_columns(text, rows, char_spacing, word_spacing)

    step = dot_diameter + dot_spacing
    radius = dot_diameter / 2
    copy_width = len(columns) * step

    copies = max(2, math.ceil(MIN_STRIP_WIDTH_PX / copy_width) + 1)
    strip_width = copy_width * copies
    grid_top = (height_px - rows * step) / 2   # centres the dot grid vertically

    # One path draws every lit dot (two arcs per circle).
    lit = []
    for c_idx, col in enumerate(columns):
        cx = c_idx * step + radius
        for r_idx, bit in enumerate(col):
            if bit == "1":
                cy = grid_top + r_idx * step + radius
                lit.append(
                    f"M{cx - radius:g},{cy:g}a{radius:g},{radius:g} 0 1,0 {dot_diameter:g},0"
                    f"a{radius:g},{radius:g} 0 1,0 -{dot_diameter:g},0"
                )
    lit_path = "".join(lit)

    uses = "".join(
        f'<use href="#copy" x="{i * copy_width}"/>' for i in range(copies)
    )

    duration = max(1.5, copy_width / speed_px_per_s)

    return f"""
    <div style="width:100%; background:{bg}; padding:{padding_px}px; border-radius:{border_radius_px}px; overflow:hidden; box-sizing:border-box;">
      <svg xmlns="http://www.w3.org/2000/svg"
           width="{strip_width}" height="{height_px}"
           viewBox="0 0 {strip_width} {height_px}"
           style="display:block;">
        <defs>
          <pattern id="unlit" width="{step}" height="{step}" patternUnits="userSpaceOnUse">
            <circle cx="{radius:g}" cy="{radius:g}" r="{radius:g}" fill="{DEFAULT_UNLIT}"/>
          </pattern>
          <path id="lit-dots" d="{lit_path}" fill="{color}"/>
          <g id="copy">
            <rect x="0" y="{grid_top}" width="{copy_width}" height="{rows * step}" fill="url(#unlit)"/>
            <use href="#lit-dots" stroke="{color}" stroke-opacity="{GLOW_OPACITY}"
                 stroke-width="{dot_diameter * GLOW_WIDTH_RATIO:g}"/>
          </g>
        </defs>

        <g id="marquee">
          {uses}
        </g>

        <style>
          @keyframes marquee-scroll {{
            from {{ transform: translateX(0); }}
            to   {{ transform: translateX(-{copy_width}px); }}
          }}
          #marquee {{
            animation: marquee-scroll {duration}s linear infinite;
          }}
        </style>
      </svg>
    </div>
    """
