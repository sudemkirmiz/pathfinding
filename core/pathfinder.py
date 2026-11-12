"""Search coordination: lifecycle, step pacing, timing and replanning.

Pygame-independent. The main loop calls ``update`` once per frame; this module
decides how many algorithm steps that frame is worth and keeps the state the
renderer displays (frontier, expanded cells, current cell, final path, hybrid
phase, and an optional BFS / A* comparison report).

State machine::

    IDLE --Space--> RUNNING --(search ends)--> FOUND | NO_PATH | VERIFICATION_FAILED
    RUNNING / REPLANNING --Space--> PAUSED --Space--> (status before pausing)

    BFS / A*: any grid edit                      -> IDLE (result discarded)
    Hybrid:   grid edit that may change the result -> REPLANNING
              REPLANNING = settle (wait for edits to stop) -> BFS check -> A* plan
              -> FOUND | NO_PATH | VERIFICATION_FAILED
    X or switching algorithm                     -> IDLE (hybrid session ends)
"""

from collections.abc import Sequence, Set
from enum import Enum, auto
from time import perf_counter

from algorithms.common import Expansion, SearchResult, SearchSteps
from algorithms.registry import STEP_FUNCTIONS, Algorithm
from core.benchmark import ComparisonReport, compare_algorithms
from core.grid import Cell, Grid
from core.hybrid import (
    HybridOutcome,
    HybridPhase,
    HybridResult,
    HybridSteps,
    PhaseStarted,
    edit_preserves_result,
    hybrid_steps,
)

# Upper bound for one frame's elapsed time, so a stalled window (e.g. while
# being dragged) does not trigger a burst of steps when it resumes.
MAX_FRAME_SECONDS = 0.25


class SearchStatus(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    REPLANNING = auto()           # Hybrid only: re-planning after a map change.
    FOUND = auto()
    NO_PATH = auto()
    VERIFICATION_FAILED = auto()  # Hybrid only: A* disagreed with BFS.


ACTIVE_STATUSES = (SearchStatus.RUNNING, SearchStatus.REPLANNING)
OUTCOME_STATUS = {
    HybridOutcome.VERIFIED: SearchStatus.FOUND,
    HybridOutcome.NO_PATH: SearchStatus.NO_PATH,
    HybridOutcome.VERIFICATION_FAILED: SearchStatus.VERIFICATION_FAILED,
}


class Pathfinder:
    """Runs the selected search incrementally and reacts to grid changes.

    Only one search generator exists at a time; it is closed before a new one
    is created, so cancelled searches can never keep running in the background.
    """

    def __init__(
        self,
        grid: Grid,
        speed_levels: Sequence[int],
        speed_index: int,
        algorithm: Algorithm = Algorithm.BFS,
        replan_settle_seconds: float = 0.0,
    ) -> None:
        if not speed_levels or not 0 <= speed_index < len(speed_levels):
            raise ValueError("speed_index must select one of speed_levels.")
        if replan_settle_seconds < 0:
            raise ValueError("replan_settle_seconds must not be negative.")
        self._grid = grid
        self._speed_levels = tuple(speed_levels)
        self._speed_index = speed_index
        self._algorithm = algorithm
        self._settle_seconds = replan_settle_seconds
        self._comparison: ComparisonReport | None = None
        self._steps: SearchSteps | HybridSteps | None = None
        self._clear()

    # --- State read by the UI ---------------------------------------------------

    @property
    def algorithm(self) -> Algorithm:
        return self._algorithm

    @property
    def comparison(self) -> ComparisonReport | None:
        """Latest comparison report, or None if there is none for the current grid."""
        report = self._comparison
        return report if report is not None and report.revision == self._grid.revision else None

    @property
    def status(self) -> SearchStatus:
        return self._status

    @property
    def phase(self) -> HybridPhase | None:
        """Current hybrid phase (None outside an active hybrid search)."""
        return self._phase

    @property
    def current(self) -> Cell | None:
        """Cell expanded by the most recent step (None when not searching)."""
        return self._current

    @property
    def frontier(self) -> Set[Cell]:
        """Discovered cells still waiting in the queue."""
        return self._frontier

    @property
    def expanded(self) -> Set[Cell]:
        """Cells already taken out of the queue and expanded."""
        return self._expanded

    @property
    def path_cells(self) -> Set[Cell]:
        return self._path_cells

    @property
    def result(self) -> SearchResult | None:
        """Final result; in hybrid mode the accepted route (None if verification failed)."""
        return self._result

    @property
    def hybrid_result(self) -> HybridResult | None:
        return self._hybrid_result

    @property
    def replan_count(self) -> int:
        """Replans started in the current hybrid session because the map changed."""
        return self._replan_count

    @property
    def routes_kept(self) -> int:
        """Edits after which the finished hybrid result provably stayed exact."""
        return self._routes_kept

    @property
    def expanded_count(self) -> int:
        return len(self._expanded)

    @property
    def discovered_count(self) -> int:
        return len(self._expanded) + len(self._frontier)

    @property
    def compute_seconds(self) -> float:
        """Time spent inside the search code for the current plan, excluding frame waits and drawing."""
        return self._compute_seconds

    @property
    def steps_per_second(self) -> int:
        return self._speed_levels[self._speed_index]

    @property
    def is_slowest(self) -> bool:
        return self._speed_index == 0

    @property
    def is_fastest(self) -> bool:
        return self._speed_index == len(self._speed_levels) - 1

    def phase_expanded_count(self, phase: HybridPhase) -> int | None:
        """Cells expanded in a hybrid phase of the current plan (None if not reached)."""
        if phase in self._phase_counts:
            return self._phase_counts[phase]
        if phase is self._phase and self._steps is not None:
            return len(self._expanded)
        return None

    # --- Controls ---------------------------------------------------------------

    def select(self, algorithm: Algorithm) -> None:
        """Choose the algorithm for the next search.

        Switching to a different algorithm discards the current search (running,
        paused or finished) and ends a hybrid session; the user starts the new
        one explicitly.
        """
        if algorithm is not self._algorithm:
            self._algorithm = algorithm
            self._clear()

    def toggle(self) -> None:
        """Start a new search (or hybrid session), or pause/resume the active one.

        Hides the comparison overlay so the animation is visible.
        """
        self._sync_with_grid()
        self._comparison = None
        if self._status in ACTIVE_STATUSES:
            self._resume_status = self._status
            self._status = SearchStatus.PAUSED
        elif self._status is SearchStatus.PAUSED:
            self._status = self._resume_status
        else:
            self._begin()

    def clear(self) -> None:
        """Drop the search, hybrid session and comparison; the grid is untouched."""
        self._clear()
        self._comparison = None

    def compare(self, repetitions: int, warmup_runs: int) -> None:
        """Benchmark BFS and A* on a snapshot of the grid without animation.

        The animated search (if any) is left exactly as it was.
        """
        self._comparison = compare_algorithms(self._grid, repetitions, warmup_runs)

    def hide_comparison(self) -> None:
        self._comparison = None

    def faster(self) -> None:
        self._speed_index = min(self._speed_index + 1, len(self._speed_levels) - 1)

    def slower(self) -> None:
        self._speed_index = max(self._speed_index - 1, 0)

    def update(self, elapsed_seconds: float) -> None:
        """React to grid changes, then advance an active search by this frame's steps."""
        self._sync_with_grid()
        if self._status not in ACTIVE_STATUSES:
            return
        elapsed_seconds = min(elapsed_seconds, MAX_FRAME_SECONDS)
        if self._phase is HybridPhase.SETTLING:
            self._settle_remaining -= elapsed_seconds
            if self._settle_remaining <= 0:
                self._replan_count += 1
                self._start_hybrid_plan(SearchStatus.REPLANNING)
            return
        self._step_budget += elapsed_seconds * self.steps_per_second
        steps = int(self._step_budget)
        self._step_budget -= steps
        for _ in range(steps):
            self.step()
            if self._status not in ACTIVE_STATUSES:
                break

    def step(self) -> None:
        """Advance the active search by exactly one event, ignoring speed."""
        self._sync_with_grid()
        if self._steps is None or self._status not in (*ACTIVE_STATUSES, SearchStatus.PAUSED):
            return
        started = perf_counter()
        try:
            event = next(self._steps)
        except StopIteration as finished:
            self._compute_seconds += perf_counter() - started
            self._finish(finished.value)
            return
        self._compute_seconds += perf_counter() - started
        if isinstance(event, PhaseStarted):
            self._enter_phase(event.phase)
        else:
            self._apply(event)

    # --- Internals --------------------------------------------------------------

    def _clear(self) -> None:
        self._close_steps()
        self._reset_search_view()
        self._status = SearchStatus.IDLE
        self._resume_status = SearchStatus.RUNNING
        self._revision: int | None = None
        self._planned_on: Grid | None = None
        self._replan_count = 0
        self._routes_kept = 0
        self._settle_remaining = 0.0

    def _reset_search_view(self) -> None:
        """Forget everything the current plan has shown or computed."""
        self._step_budget = 0.0
        self._compute_seconds = 0.0
        self._current: Cell | None = None
        self._frontier: set[Cell] = set()
        self._expanded: set[Cell] = set()
        self._path_cells: frozenset[Cell] = frozenset()
        self._result: SearchResult | None = None
        self._hybrid_result: HybridResult | None = None
        self._phase: HybridPhase | None = None
        self._phase_counts: dict[HybridPhase, int] = {}

    def _close_steps(self) -> None:
        if self._steps is not None:
            self._steps.close()
            self._steps = None

    def _begin(self) -> None:
        self._clear()
        if self._algorithm is Algorithm.HYBRID:
            self._start_hybrid_plan(SearchStatus.RUNNING)
            return
        self._steps = STEP_FUNCTIONS[self._algorithm](self._grid)
        self._revision = self._grid.revision
        self._frontier.add(self._grid.start)
        self._status = SearchStatus.RUNNING

    def _start_hybrid_plan(self, status: SearchStatus) -> None:
        """Start a fresh hybrid plan on a snapshot of the current grid."""
        self._close_steps()
        self._reset_search_view()
        self._planned_on = self._grid.copy()
        self._revision = self._planned_on.revision
        self._steps = hybrid_steps(self._planned_on)
        self._status = status

    def _sync_with_grid(self) -> None:
        """React to a grid revision change: discard (BFS / A*) or replan (hybrid)."""
        if self._comparison is not None and self._comparison.revision != self._grid.revision:
            self._comparison = None
        if self._status is SearchStatus.IDLE or self._revision == self._grid.revision:
            return
        if self._algorithm is not Algorithm.HYBRID:
            self._clear()
            return

        # Policy: a finished hybrid result is kept only when the edit provably
        # cannot change it (walls added off the route, endpoints unchanged).
        if (
            self._status in (SearchStatus.FOUND, SearchStatus.NO_PATH)
            and self._planned_on is not None
            and self._result is not None
            and edit_preserves_result(self._planned_on, self._grid, self._result.path)
        ):
            self._planned_on = self._grid.copy()
            self._revision = self._planned_on.revision
            self._routes_kept += 1
            return
        self._schedule_replan()

    def _schedule_replan(self) -> None:
        """Cancel the outdated plan, hide its route, and wait for edits to settle.

        Every further edit restarts the wait, so a burst of edits (e.g. one
        mouse stroke) is coalesced into a single replan.
        """
        self._close_steps()
        self._reset_search_view()
        self._phase = HybridPhase.SETTLING
        self._settle_remaining = self._settle_seconds
        self._revision = self._grid.revision
        if self._status is SearchStatus.PAUSED:
            self._resume_status = SearchStatus.REPLANNING
        else:
            self._status = SearchStatus.REPLANNING

    def _enter_phase(self, phase: HybridPhase) -> None:
        """Switch to a new hybrid phase, clearing the previous phase's exploration."""
        if self._phase is not None:
            self._phase_counts[self._phase] = len(self._expanded)
        self._phase = phase
        self._current = None
        self._expanded.clear()
        self._frontier = {self._planned_on.start} if self._planned_on else set()

    def _apply(self, expansion: Expansion) -> None:
        self._current = expansion.cell
        self._frontier.discard(expansion.cell)
        self._expanded.add(expansion.cell)
        self._frontier.update(expansion.discovered)

    def _finish(self, result: SearchResult | HybridResult) -> None:
        self._steps = None
        self._current = None
        if isinstance(result, HybridResult):
            self._phase_counts[self._phase] = len(self._expanded)
            self._phase = None
            self._hybrid_result = result
            self._result = result.route
            self._status = OUTCOME_STATUS[result.outcome]
        else:
            self._result = result
            self._status = SearchStatus.FOUND if result.found else SearchStatus.NO_PATH
        self._path_cells = frozenset(self._result.path) if self._result else frozenset()
