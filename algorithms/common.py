"""Search event and result types shared by every grid search algorithm."""

from collections.abc import Generator
from dataclasses import dataclass

from core.grid import Cell


@dataclass(frozen=True, slots=True)
class Expansion:
    """One search step: ``cell`` was taken from the frontier and expanded.

    Attributes:
        cell: The expanded cell.
        discovered: Cells reached for the first time during this step.
        improved: Already-discovered frontier cells that got a shorter known
            route in this step (A* only; BFS never improves a cell). They are
            not new discoveries and must not be counted again.
    """

    cell: Cell
    discovered: tuple[Cell, ...]
    improved: tuple[Cell, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Outcome of a finished search.

    Attributes:
        path: Cells from start to target inclusive, or empty if unreachable.
        expanded_count: Unique cells taken from the frontier and expanded.
        discovered_count: Unique cells ever reached, including the start.
    """

    path: tuple[Cell, ...]
    expanded_count: int
    discovered_count: int

    @property
    def found(self) -> bool:
        return bool(self.path)

    @property
    def path_length(self) -> int | None:
        """Number of moves on the path, or None if no path exists."""
        return len(self.path) - 1 if self.path else None


# A search runs as a generator: it yields one Expansion per step and returns
# the SearchResult as its StopIteration value.
SearchSteps = Generator[Expansion, None, SearchResult]


def run_to_completion(steps: SearchSteps) -> SearchResult:
    """Drive a search generator to the end without animation."""
    while True:
        try:
            next(steps)
        except StopIteration as finished:
            return finished.value


def reconstruct_path(parent: dict[Cell, Cell], start: Cell, target: Cell) -> tuple[Cell, ...]:
    """Follow ``parent`` links back from ``target`` to ``start``; return start→target."""
    path = [target]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return tuple(path)
