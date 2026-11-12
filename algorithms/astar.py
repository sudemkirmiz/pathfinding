"""A* search on a 4-connected grid with unit move costs and a Manhattan heuristic.

Pure Python, no Pygame. Like BFS it is a generator yielding one ``Expansion``
per expanded cell, so both algorithms share the same animation pipeline.
"""

import heapq
from itertools import count

from algorithms.common import Expansion, SearchResult, SearchSteps, reconstruct_path, run_to_completion
from core.grid import Cell, Grid

MOVE_COST = 1


def manhattan_distance(a: Cell, b: Cell) -> int:
    """Admissible and consistent heuristic for 4-directional unit-cost moves."""
    return abs(a.row - b.row) + abs(a.col - b.col)


def astar_steps(grid: Grid) -> SearchSteps:
    """Run A* from ``grid.start`` to ``grid.target``, yielding each expansion.

    Priority is ``f = g + h``. Ties are broken deterministically by:
        1. lower ``f`` (estimated total cost),
        2. lower ``h`` (closer to the target, so the search dives toward it),
        3. earlier insertion into the heap (FIFO), which in turn follows the
           fixed ``Grid.neighbors`` order (up, down, left, right).

    A cell's ``g`` can improve while it is still in the frontier; it is then
    pushed again and the older heap entry becomes *stale*. Stale entries are
    skipped when popped because their cell is already in ``closed``: with a
    consistent heuristic the first pop of a cell carries its optimal ``g``.

    The search ends when the target is popped. The target is counted as
    discovered but not expanded (its neighbours are never examined), which
    matches the BFS convention and keeps the statistics comparable.
    """
    start, target = grid.start, grid.target
    if start == target:
        return SearchResult(path=(start,), expanded_count=0, discovered_count=1)

    insertion_order = count()
    start_h = manhattan_distance(start, target)
    frontier: list[tuple[int, int, int, Cell]] = [(start_h, start_h, next(insertion_order), start)]
    g_score: dict[Cell, int] = {start: 0}  # Best known cost from start; keys = discovered cells.
    parent: dict[Cell, Cell] = {}           # parent[c] = predecessor on the best known route.
    closed: set[Cell] = set()               # Expanded cells; never expanded twice.

    while frontier:
        _, _, _, cell = heapq.heappop(frontier)
        if cell in closed:
            continue  # Stale entry left behind by a later improvement.
        if cell == target:
            return SearchResult(reconstruct_path(parent, start, target), len(closed), len(g_score))

        closed.add(cell)
        discovered: list[Cell] = []
        improved: list[Cell] = []
        for neighbor in grid.neighbors(cell):
            if neighbor in closed:
                continue
            tentative_g = g_score[cell] + MOVE_COST
            known_g = g_score.get(neighbor)
            if known_g is not None and tentative_g >= known_g:
                continue
            g_score[neighbor] = tentative_g
            parent[neighbor] = cell
            h = manhattan_distance(neighbor, target)
            heapq.heappush(frontier, (tentative_g + h, h, next(insertion_order), neighbor))
            (discovered if known_g is None else improved).append(neighbor)
        yield Expansion(cell, tuple(discovered), tuple(improved))

    return SearchResult(path=(), expanded_count=len(closed), discovered_count=len(g_score))


def astar(grid: Grid) -> SearchResult:
    """Run A* to completion without animation and return the result."""
    return run_to_completion(astar_steps(grid))
