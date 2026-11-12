"""Text shown in the header, info cards and comparison overlay, plus value formatting.

Pure Python (no Pygame).
"""

from algorithms.registry import Algorithm
from core.benchmark import ComparisonReport
from core.grid import Grid
from core.hybrid import HybridPhase
from core.pathfinder import Pathfinder, SearchStatus
from ui import theme
from ui.controls import HYBRID_FOUND_TEXT, HYBRID_PHASE_TEXT, STATUS_TEXT, Tone, status_text
from ui.theme import Color

SUBTITLE = "Grid path planning with BFS, A* and a verified hybrid"
NO_VALUE = "—"
MILLISECONDS_PER_SECOND = 1000
# Width reserved for the computation time ("9999.000 ms"); a 20x50 search takes a few ms.
WIDEST_COMPUTE_SECONDS = 9.999
MAX_DISPLAYED_REPLANS = 99999  # Width reserved for the replan counter.

LEGEND: tuple[tuple[str, Color], ...] = (
    ("Start", theme.START_COLOR),
    ("Target", theme.TARGET_COLOR),
    ("Wall", theme.WALL_COLOR),
    ("Empty", theme.EMPTY_CELL_COLOR),
    ("Frontier", theme.FRONTIER_COLOR),
    ("Expanded", theme.EXPANDED_COLOR),
    ("Current", theme.CURRENT_COLOR),
    ("Path", theme.PATH_COLOR),
)
SHORTCUT_COLUMNS: tuple[tuple[tuple[str, str], ...], ...] = (
    (
        ("Left drag", "Add walls"),
        ("Right drag", "Erase walls"),
        ("Drag S / T", "Move endpoints"),
        ("C / R", "Clear walls / reset"),
        ("Esc", "Quit"),
    ),
    (
        ("Space", "Start / pause"),
        ("1 / 2 / 3", "Select mode"),
        ("↑ / ↓", "Speed"),
        ("X", "Clear search"),
        ("B", "Compare"),
    ),
)
STATUS_LABEL = "Status"
STAT_LABELS: tuple[str, ...] = (STATUS_LABEL, "Expanded", "Discovered", "Path", "Time", "Walls")
HYBRID_STAT_LABELS: tuple[str, ...] = (STATUS_LABEL, "BFS expanded", "A* expanded", "Path", "Replans", "Time")
# One statistics row: label, value, and the status tone used to color the value (if any).
StatRow = tuple[str, str, Tone | None]

COMPARISON_TITLE = "BFS VS A*  ·  SAME GRID SNAPSHOT"
COMPARISON_ROW_LABELS: tuple[str, ...] = ("Result", "Path", "Expanded", "Discovered", "Median time")
COMPARISON_CLOSE_HINT = "Press B or X to close"


def comparison_note(report: ComparisonReport) -> str:
    return (
        f"Median of {report.repetitions} runs after {report.warmup_runs} warm-ups, "
        "without animation. Times are approximate."
    )


def format_milliseconds(seconds: float) -> str:
    return f"{seconds * MILLISECONDS_PER_SECOND:.3f} ms"


def format_moves(moves: int) -> str:
    return f"{moves} move" if moves == 1 else f"{moves} moves"


def format_path(path_length: int | None) -> str:
    return "No path" if path_length is None else format_moves(path_length)


def format_speed(steps_per_second: int) -> str:
    return f"{steps_per_second} steps/s"


def widest_stat_values(rows: int, cols: int) -> tuple[str, ...]:
    """The widest text any statistic can show, used to size the card."""
    cell_count = rows * cols
    return (
        str(cell_count),
        format_moves(cell_count),
        format_milliseconds(WIDEST_COMPUTE_SECONDS),
        f"{cell_count} / {cell_count}",
        str(MAX_DISPLAYED_REPLANS),
        format_path(None),
        *(text for text, _ in STATUS_TEXT.values()),
        *HYBRID_PHASE_TEXT.values(),
        HYBRID_FOUND_TEXT,
    )


def stat_rows(grid: Grid, pathfinder: Pathfinder) -> tuple[StatRow, ...]:
    """Rows of the statistics card in the current mode; the first one is the status."""
    if pathfinder.algorithm is Algorithm.HYBRID:
        labels, values = HYBRID_STAT_LABELS[1:], _hybrid_values(pathfinder)
    else:
        labels, values = STAT_LABELS[1:], _plain_values(grid, pathfinder)
    status, tone = status_text(pathfinder)
    return ((STATUS_LABEL, status, tone), *((label, value, None) for label, value in zip(labels, values)))


def _plain_values(grid: Grid, pathfinder: Pathfinder) -> tuple[str, ...]:
    walls = f"{grid.wall_count} / {grid.rows * grid.cols}"
    if pathfinder.status is SearchStatus.IDLE:
        return NO_VALUE, NO_VALUE, NO_VALUE, NO_VALUE, walls
    result = pathfinder.result
    return (
        str(pathfinder.expanded_count),
        str(pathfinder.discovered_count),
        NO_VALUE if result is None else format_path(result.path_length),
        format_milliseconds(pathfinder.compute_seconds),
        walls,
    )


def _hybrid_values(pathfinder: Pathfinder) -> tuple[str, ...]:
    def count(phase: HybridPhase) -> str:
        value = pathfinder.phase_expanded_count(phase)
        return NO_VALUE if value is None else str(value)

    result = pathfinder.result
    finished = pathfinder.status in (SearchStatus.FOUND, SearchStatus.NO_PATH)
    searched = pathfinder.status is not SearchStatus.IDLE and pathfinder.phase is not HybridPhase.SETTLING
    return (
        count(HybridPhase.BFS_CHECK),
        count(HybridPhase.ASTAR_PLAN),
        format_path(result.path_length) if finished and result is not None else NO_VALUE,
        str(pathfinder.replan_count),
        format_milliseconds(pathfinder.compute_seconds) if searched else NO_VALUE,
    )
