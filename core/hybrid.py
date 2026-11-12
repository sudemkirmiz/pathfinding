"""Hybrid mode: A* route planning cross-checked by a BFS reachability/distance pass.

Purpose: *verified planning*. A* (Manhattan heuristic) plans the route, and an
independent BFS pass certifies (1) whether the target is reachable at all and
(2) the true shortest distance. A route is only accepted when it is a valid
walkable 4-neighbour path whose length equals the BFS distance. This trades
extra computation for an independent correctness check, the way a safety
monitor double-checks a planner; it is not meant to be faster than A* alone.

This is NOT D* Lite, LPA* or any other incremental search (every plan starts
from scratch on a fresh grid snapshot), and NOT Hybrid A* (no vehicle
kinematics or continuous states). Replanning on map changes is handled by
``core.pathfinder``.

Pygame-independent. Both algorithms are reused via ``yield from``; none of
their logic is duplicated here.
"""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from enum import Enum, auto

from algorithms.astar import astar_steps
from algorithms.bfs import bfs_steps
from algorithms.common import Expansion, SearchResult, SearchSteps
from core.grid import Cell, Grid


class HybridPhase(Enum):
    SETTLING = auto()   # Map just changed; waiting for edits to settle before replanning.
    BFS_CHECK = auto()  # BFS: reachability and reference shortest distance.
    ASTAR_PLAN = auto() # A*: route planning.


class HybridOutcome(Enum):
    VERIFIED = auto()             # A* route is valid and as short as BFS proves possible.
    NO_PATH = auto()              # BFS proved the target unreachable; A* was skipped.
    VERIFICATION_FAILED = auto()  # A* disagreed with BFS; the route is rejected.


@dataclass(frozen=True, slots=True)
class PhaseStarted:
    """Marker event: the hybrid search moved on to ``phase``."""

    phase: HybridPhase


@dataclass(frozen=True, slots=True)
class HybridResult:
    outcome: HybridOutcome
    bfs: SearchResult
    astar: SearchResult | None  # None when A* was skipped (target unreachable).

    @property
    def route(self) -> SearchResult | None:
        """The accepted route: the A* result if verified, the BFS proof if unreachable."""
        if self.outcome is HybridOutcome.VERIFIED:
            return self.astar
        if self.outcome is HybridOutcome.NO_PATH:
            return self.bfs
        return None


HybridEvent = Expansion | PhaseStarted
HybridSteps = Generator[HybridEvent, None, HybridResult]


def hybrid_steps(
    grid: Grid,
    verifier: Callable[[Grid], SearchSteps] = bfs_steps,
    planner: Callable[[Grid], SearchSteps] = astar_steps,
) -> HybridSteps:
    """Run the BFS check, then A* planning, then verification; yield every step.

    ``verifier`` and ``planner`` are injectable so tests can simulate a faulty
    planner. ``grid`` should be a snapshot that nobody edits while this runs.
    """
    yield PhaseStarted(HybridPhase.BFS_CHECK)
    reference = yield from verifier(grid)
    if not reference.found:
        return HybridResult(HybridOutcome.NO_PATH, reference, None)

    yield PhaseStarted(HybridPhase.ASTAR_PLAN)
    plan = yield from planner(grid)
    verified = plan.path_length == reference.path_length and is_valid_route(grid, plan.path)
    outcome = HybridOutcome.VERIFIED if verified else HybridOutcome.VERIFICATION_FAILED
    return HybridResult(outcome, reference, plan)


def is_valid_route(grid: Grid, path: tuple[Cell, ...]) -> bool:
    """True if ``path`` runs from start to target over walkable 4-neighbour steps."""
    if not path or path[0] != grid.start or path[-1] != grid.target:
        return False
    if not all(grid.is_walkable(cell) for cell in path):
        return False
    return all(abs(a.row - b.row) + abs(a.col - b.col) == 1 for a, b in zip(path, path[1:]))


def edit_preserves_result(planned_on: Grid, current: Grid, route: tuple[Cell, ...]) -> bool:
    """Whether a finished result for ``planned_on`` is still exact for ``current``.

    True only if the endpoints are unchanged, no wall was removed, and no added
    wall lies on ``route``. Adding walls can never create a shorter path, so a
    still-walkable optimal route stays optimal, and an unreachable target stays
    unreachable. Removing a wall may open a shorter route, so it returns False.
    """
    if (planned_on.start, planned_on.target) != (current.start, current.target):
        return False
    if not planned_on.walls <= current.walls:
        return False
    return current.walls.isdisjoint(route)
