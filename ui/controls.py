"""Toolbar buttons and status wording: what each control shows and whether it can be used.

Pure Python (no Pygame): ``main`` uses it to handle clicks, the renderer to
draw, and the tests can check it directly.
"""

from enum import Enum, auto

from algorithms.registry import Algorithm
from core.hybrid import HybridPhase
from core.pathfinder import ACTIVE_STATUSES, Pathfinder, SearchStatus


class Button(Enum):
    BFS = auto()
    ASTAR = auto()
    HYBRID = auto()
    START = auto()
    CLEAR = auto()
    COMPARE = auto()
    SLOWER = auto()
    FASTER = auto()


class Tone(Enum):
    """Meaning of a status, mapped to a color by the renderer."""

    NEUTRAL = auto()
    ACTIVE = auto()
    WARNING = auto()
    SUCCESS = auto()
    ERROR = auto()


MODE_BUTTONS: dict[Button, Algorithm] = {
    Button.BFS: Algorithm.BFS,
    Button.ASTAR: Algorithm.ASTAR,
    Button.HYBRID: Algorithm.HYBRID,
}
BUTTON_LABELS: dict[Button, str] = {
    Button.BFS: Algorithm.BFS.value,
    Button.ASTAR: Algorithm.ASTAR.value,
    Button.HYBRID: Algorithm.HYBRID.value,
    Button.CLEAR: "Clear",
    Button.COMPARE: "Compare",
    Button.SLOWER: "−",
    Button.FASTER: "+",
}
START_LABELS = ("Start", "Pause", "Resume")

STATUS_TEXT: dict[SearchStatus, tuple[str, Tone]] = {
    SearchStatus.IDLE: ("Ready", Tone.NEUTRAL),
    SearchStatus.RUNNING: ("Searching", Tone.ACTIVE),
    SearchStatus.PAUSED: ("Paused", Tone.WARNING),
    SearchStatus.REPLANNING: ("Replanning", Tone.WARNING),
    SearchStatus.FOUND: ("Path found", Tone.SUCCESS),
    SearchStatus.NO_PATH: ("No path", Tone.ERROR),
    SearchStatus.VERIFICATION_FAILED: ("Verification failed", Tone.ERROR),
}
PAUSED_REPLAN_TEXT = "Replan pending"
# Hybrid wording by (status, phase); combinations not listed use STATUS_TEXT.
HYBRID_PHASE_TEXT: dict[tuple[SearchStatus, HybridPhase], str] = {
    (SearchStatus.RUNNING, HybridPhase.BFS_CHECK): "BFS check",
    (SearchStatus.RUNNING, HybridPhase.ASTAR_PLAN): "A* planning",
    (SearchStatus.REPLANNING, HybridPhase.SETTLING): "Map changed",
    (SearchStatus.REPLANNING, HybridPhase.BFS_CHECK): "Replan · BFS check",
    (SearchStatus.REPLANNING, HybridPhase.ASTAR_PLAN): "Replan · A* planning",
    (SearchStatus.PAUSED, HybridPhase.SETTLING): PAUSED_REPLAN_TEXT,
}
HYBRID_FOUND_TEXT = "Route verified"


def status_text(pathfinder: Pathfinder) -> tuple[str, Tone]:
    """Short status such as "Path found", or "A* planning" for a hybrid phase."""
    text, tone = STATUS_TEXT[pathfinder.status]
    if pathfinder.algorithm is Algorithm.HYBRID:
        if pathfinder.status is SearchStatus.FOUND:
            text = HYBRID_FOUND_TEXT
        elif pathfinder.phase is not None:
            text = HYBRID_PHASE_TEXT.get((pathfinder.status, pathfinder.phase), text)
    return text, tone


def is_busy(pathfinder: Pathfinder) -> bool:
    """True while a search or replan is actively running."""
    return pathfinder.status in ACTIVE_STATUSES


def start_button_label(pathfinder: Pathfinder) -> str:
    if is_busy(pathfinder):
        return "Pause"
    if pathfinder.status is SearchStatus.PAUSED:
        return "Resume"
    return "Start"


def is_button_enabled(button: Button, pathfinder: Pathfinder) -> bool:
    """Whether clicking ``button`` would do anything in the current state."""
    if button is Button.CLEAR:
        return pathfinder.status is not SearchStatus.IDLE or pathfinder.comparison is not None
    if button is Button.SLOWER:
        return not pathfinder.is_slowest
    if button is Button.FASTER:
        return not pathfinder.is_fastest
    return True


def is_button_active(button: Button, pathfinder: Pathfinder) -> bool:
    """Selected / toggled-on state: the chosen mode, or a visible comparison."""
    if button in MODE_BUTTONS:
        return pathfinder.algorithm is MODE_BUTTONS[button]
    if button is Button.COMPARE:
        return pathfinder.comparison is not None
    return False
