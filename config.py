"""Application settings: grid size, search pacing, replanning and benchmark parameters.

Visual design values (colors, fonts, spacing, animation timing) live in
``ui/theme.py``.
"""

from typing import Final

# --- Application -------------------------------------------------------------
WINDOW_TITLE: Final = "Pathfinding"
FPS: Final = 60

# --- Search animation --------------------------------------------------------
# Selectable animation speeds in search steps per second (Up/Down arrows).
SPEED_LEVELS: Final = (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000)
DEFAULT_SPEED_INDEX: Final = 6

# --- Hybrid replanning ---------------------------------------------------------
# After a map edit, wait until no further edit happened for this long before
# replanning, so a mouse stroke over many cells triggers one replan, not dozens.
REPLAN_SETTLE_SECONDS: Final = 0.3

# --- Algorithm comparison (B key) ----------------------------------------------
COMPARISON_REPETITIONS: Final = 20  # Timed runs per algorithm; the median is shown.
COMPARISON_WARMUP_RUNS: Final = 3   # Untimed runs per algorithm before timing.

# --- Grid model --------------------------------------------------------------
GRID_ROWS: Final = 20
GRID_COLS: Final = 50
# (row, col) of the default endpoints: vertically centered, horizontally inset.
DEFAULT_START: Final = (GRID_ROWS // 2, GRID_COLS // 5)
DEFAULT_TARGET: Final = (GRID_ROWS // 2, GRID_COLS - 1 - GRID_COLS // 5)
