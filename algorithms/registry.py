"""The selectable search modes and the step generators of the plain algorithms."""

from collections.abc import Callable
from enum import Enum

from algorithms.astar import astar_steps
from algorithms.bfs import bfs_steps
from algorithms.common import SearchSteps
from core.grid import Grid


class Algorithm(Enum):
    """Selectable mode; the value is its display name.

    HYBRID is orchestrated in ``core.hybrid`` / ``core.pathfinder`` and has no
    entry in ``STEP_FUNCTIONS``: it combines the two plain algorithms.
    """

    BFS = "BFS"
    ASTAR = "A*"
    HYBRID = "Hybrid"


# Plain single-algorithm searches (also the set compared by core.benchmark).
STEP_FUNCTIONS: dict[Algorithm, Callable[[Grid], SearchSteps]] = {
    Algorithm.BFS: bfs_steps,
    Algorithm.ASTAR: astar_steps,
}
