"""Design tokens: colors, typography, spacing and animation timing.

Pure constants (no Pygame), shared by every UI module. Sizes below are base
values at scale 1.0; ``apply_scale`` multiplies them once at startup so the UI
is drawn crisply at the display's real resolution. Other modules read them as
``theme.NAME`` at draw time, so they always see the scaled value.
"""

from typing import Final

Color = tuple[int, int, int]

# --- Typography (scaled) -------------------------------------------------------
# Comma-separated SysFont fallbacks; pygame uses its default font if none exist.
FONT_NAME: Final = "segoeui,helveticaneue,arial"
TITLE_FONT_SIZE = 22
SUBTITLE_FONT_SIZE = 13
TEXT_FONT_SIZE = 14
BUTTON_FONT_SIZE = 14
SMALL_FONT_SIZE = 12
HEADING_FONT_SIZE = 11
CELL_LABEL_FONT_SIZE = 12

# --- Grid geometry (scaled) ------------------------------------------------------
CELL_SIZE = 21          # Square cell pitch, including the gap.
CELL_GAP = 2            # Space between neighbouring cells.
CELL_RADIUS = 3
HOVER_BORDER_WIDTH = 2

# --- Page layout (scaled) ----------------------------------------------------------
PAGE_MARGIN = 16        # Distance from the window edge to every block.
SECTION_GAP = 12        # Vertical space between toolbar, grid and cards.
HEADER_HEIGHT = 58
LOGO_SIZE = 26
LOGO_RADIUS = 7
LOGO_DOT_RADIUS = 3
LOGO_LINE_WIDTH = 2
LOGO_TEXT_GAP = 12

# --- Toolbar (scaled) --------------------------------------------------------------
TOOLBAR_HEIGHT = 34
BUTTON_RADIUS = 8
BUTTON_PADDING_X = 16
BUTTON_GAP = 8          # Space between neighbouring standalone buttons.
GROUP_GAP = 20          # Space between toolbar groups.
GROUP_INSET = 3         # Padding inside the segmented and speed groups.
SPEED_LABEL_PADDING = 10
BORDER_WIDTH = 1

# --- Cards (scaled) ----------------------------------------------------------------
CARD_RADIUS = 12
GRID_CARD_PADDING = 8   # Space between the grid card's border and the cells.
CARD_PADDING = 16
CARD_GAP = 12           # Horizontal space between the bottom cards.
CARD_HEADING_GAP = 8    # Space below a card heading.
LINE_SPACING = 21       # Vertical distance between card rows.
PAIR_GAP = 12           # Space between a label/key and its value.
CARD_COLUMN_GAP = 24    # Space between columns inside one card.
SWATCH_SIZE = 12
SWATCH_TEXT_GAP = 10
KEYCAP_PADDING_X = 6
KEYCAP_HEIGHT = 18
KEYCAP_RADIUS = 4

# --- Comparison overlay (scaled) -----------------------------------------------------
OVERLAY_PADDING = 22
OVERLAY_COLUMN_GAP = 36
OVERLAY_ROW_SPACING = 26
OVERLAY_NOTE_GAP = 10
OVERLAY_RADIUS = 14

SCALED_NAMES: Final = (
    "TITLE_FONT_SIZE", "SUBTITLE_FONT_SIZE", "TEXT_FONT_SIZE", "BUTTON_FONT_SIZE", "SMALL_FONT_SIZE",
    "HEADING_FONT_SIZE", "CELL_LABEL_FONT_SIZE",
    "CELL_SIZE", "CELL_GAP", "CELL_RADIUS", "HOVER_BORDER_WIDTH",
    "PAGE_MARGIN", "SECTION_GAP", "HEADER_HEIGHT", "LOGO_SIZE", "LOGO_RADIUS", "LOGO_DOT_RADIUS",
    "LOGO_LINE_WIDTH", "LOGO_TEXT_GAP",
    "TOOLBAR_HEIGHT", "BUTTON_RADIUS", "BUTTON_PADDING_X", "BUTTON_GAP", "GROUP_GAP", "GROUP_INSET",
    "SPEED_LABEL_PADDING", "BORDER_WIDTH",
    "CARD_RADIUS", "GRID_CARD_PADDING", "CARD_PADDING", "CARD_GAP", "CARD_HEADING_GAP", "LINE_SPACING",
    "PAIR_GAP", "CARD_COLUMN_GAP", "SWATCH_SIZE", "SWATCH_TEXT_GAP", "KEYCAP_PADDING_X", "KEYCAP_HEIGHT",
    "KEYCAP_RADIUS",
    "OVERLAY_PADDING", "OVERLAY_COLUMN_GAP", "OVERLAY_ROW_SPACING", "OVERLAY_NOTE_GAP", "OVERLAY_RADIUS",
)
_BASE_SIZES: Final = {name: globals()[name] for name in SCALED_NAMES}
scale = 1.0


def apply_scale(factor: float) -> None:
    """Set every size token to its base value times ``factor`` (at least 1 px)."""
    global scale
    if factor <= 0:
        raise ValueError("UI scale must be positive.")
    scale = factor
    for name, base in _BASE_SIZES.items():
        globals()[name] = max(1, round(base * factor))


# --- Unscaled values -------------------------------------------------------------------
LEGEND_COLUMNS: Final = 2
OVERLAY_DIM_ALPHA: Final = 190     # 0-255 dimming of the grid behind the comparison card.

# Animation (milliseconds).
CELL_FADE_MS: Final = 160          # Search-state color change of a cell.
PATH_REVEAL_TOTAL_MS: Final = 600  # Time for the final path to grow from start to target.
PATH_REVEAL_STEP_MAX_MS: Final = 18
HOVER_FADE_MS: Final = 120
OVERLAY_FADE_MS: Final = 180

# --- Colors: surfaces --------------------------------------------------------
BACKGROUND_COLOR: Final[Color] = (13, 16, 23)
SURFACE_COLOR: Final[Color] = (20, 24, 33)          # Cards.
RAISED_COLOR: Final[Color] = (28, 33, 45)           # Buttons, keycaps, groups.
HOVER_SURFACE_COLOR: Final[Color] = (38, 45, 61)
BORDER_COLOR: Final[Color] = (36, 43, 58)
STRONG_BORDER_COLOR: Final[Color] = (52, 61, 80)
GRID_BACKGROUND_COLOR: Final[Color] = (16, 20, 28)

# --- Colors: text --------------------------------------------------------------
TITLE_COLOR: Final[Color] = (236, 240, 247)
TEXT_COLOR: Final[Color] = (214, 220, 231)
MUTED_TEXT_COLOR: Final[Color] = (139, 150, 171)
HEADING_COLOR: Final[Color] = (112, 124, 147)
DISABLED_TEXT_COLOR: Final[Color] = (78, 87, 106)

# --- Colors: accent and status ---------------------------------------------------
ACCENT_COLOR: Final[Color] = (64, 125, 255)
ACCENT_HOVER_COLOR: Final[Color] = (92, 146, 255)
ACCENT_TEXT_COLOR: Final[Color] = (148, 184, 255)   # Accent-colored text on dark surfaces.
ON_ACCENT_COLOR: Final[Color] = (255, 255, 255)

NEUTRAL_STATUS_COLOR: Final[Color] = MUTED_TEXT_COLOR
ACTIVE_STATUS_COLOR: Final[Color] = (96, 156, 255)
WARNING_COLOR: Final[Color] = (236, 174, 66)
SUCCESS_COLOR: Final[Color] = (52, 196, 132)
ERROR_COLOR: Final[Color] = (236, 92, 92)

# --- Colors: grid cells ------------------------------------------------------------
EMPTY_CELL_COLOR: Final[Color] = (31, 37, 50)
WALL_COLOR: Final[Color] = (84, 94, 114)
START_COLOR: Final[Color] = SUCCESS_COLOR
TARGET_COLOR: Final[Color] = ERROR_COLOR
FRONTIER_COLOR: Final[Color] = (58, 112, 214)       # Discovered, waiting in the queue.
EXPANDED_COLOR: Final[Color] = (33, 58, 104)        # Already expanded.
CURRENT_COLOR: Final[Color] = (134, 190, 255)       # Expanded in the latest step.
PATH_COLOR: Final[Color] = (242, 183, 64)
HOVER_COLOR: Final[Color] = (226, 232, 242)
CELL_LABEL_COLOR: Final[Color] = BACKGROUND_COLOR
