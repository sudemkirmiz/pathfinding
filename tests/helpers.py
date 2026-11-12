"""Shared helpers for the algorithm tests."""

import random
import unittest
from collections.abc import Callable, Sequence

from algorithms.common import Expansion, SearchResult, SearchSteps
from core.grid import Cell, Grid


def make_grid(rows: int, cols: int, start: Cell, target: Cell, walls: Sequence[Cell] = ()) -> Grid:
    grid = Grid(rows, cols, start, target)
    for wall in walls:
        grid.add_wall(wall)
    return grid


def random_grid(seed: int, max_size: int = 9, max_density: float = 0.5) -> Grid:
    """Deterministic random grid: size, endpoints and wall density all come from ``seed``."""
    rng = random.Random(seed)
    rows, cols = rng.randint(2, max_size), rng.randint(2, max_size)
    cells = [Cell(r, c) for r in range(rows) for c in range(cols)]
    start, target = rng.sample(cells, 2)
    density = rng.uniform(0.0, max_density)
    return make_grid(rows, cols, start, target, [cell for cell in cells if rng.random() < density])


def collect(grid: Grid, step_function: Callable[[Grid], SearchSteps]) -> tuple[list[Expansion], SearchResult]:
    """Run a search generator and return (all yielded events, final result)."""
    events: list[Expansion] = []
    steps = step_function(grid)
    while True:
        try:
            events.append(next(steps))
        except StopIteration as finished:
            return events, finished.value


def fake_planner(path: tuple[Cell, ...]) -> Callable[[Grid], SearchSteps]:
    """A planner that skips searching and claims ``path`` (simulates a buggy planner)."""
    def planner(grid: Grid) -> SearchSteps:
        yield from ()
        return SearchResult(path, expanded_count=0, discovered_count=0)
    return planner


def reference_distance(grid: Grid) -> int | None:
    """Independent shortest-distance check by repeated relaxation (no queue).

    Bellman-Ford style: keep lowering dist[c] to min(neighbour + 1) until stable.
    Deliberately structured differently from BFS and A* so they can cross-check.
    """
    infinity = grid.rows * grid.cols
    cells = [Cell(r, c) for r in range(grid.rows) for c in range(grid.cols) if grid.is_walkable(Cell(r, c))]
    dist = {cell: infinity for cell in cells}
    dist[grid.start] = 0
    changed = True
    while changed:
        changed = False
        for cell in cells:
            best = min((dist[n] + 1 for n in grid.neighbors(cell)), default=infinity)
            if best < dist[cell]:
                dist[cell] = best
                changed = True
    return None if dist[grid.target] >= infinity else dist[grid.target]


def assert_valid_path(test: unittest.TestCase, grid: Grid, path: tuple[Cell, ...]) -> None:
    test.assertEqual(path[0], grid.start)
    test.assertEqual(path[-1], grid.target)
    test.assertEqual(len(set(path)), len(path), "path must not repeat cells")
    for cell in path:
        test.assertTrue(grid.is_walkable(cell), f"{cell} is a wall or out of bounds")
    for a, b in zip(path, path[1:]):
        test.assertEqual(abs(a.row - b.row) + abs(a.col - b.col), 1, f"{a}->{b} is not a 4-neighbour move")
