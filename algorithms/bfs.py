"""Breadth-first search on a 4-connected grid with unit move costs.

Pure Python, no Pygame. The search is written as a generator so a caller can
advance it one expansion at a time (for animation) or run it to completion.
"""

from collections import deque

from algorithms.common import Expansion, SearchResult, SearchSteps, reconstruct_path, run_to_completion
from core.grid import Cell, Grid


def bfs_steps(grid: Grid) -> SearchSteps:
    """Run BFS from ``grid.start`` to ``grid.target``, yielding each expansion.

    The final ``SearchResult`` is the generator's return value
    (``StopIteration.value``). Neighbours are explored in ``Grid.neighbors``
    order (up, down, left, right), so results are deterministic.

    The search stops as soon as the target is *discovered*: in BFS every cell
    is first discovered at its shortest distance, so waiting until the target
    is dequeued would only expand extra cells without changing the path.
    """
    start, target = grid.start, grid.target
    if start == target:
        return SearchResult(path=(start,), expanded_count=0, discovered_count=1)

    queue: deque[Cell] = deque([start])
    visited: set[Cell] = {start}       # Every cell ever enqueued; each enters once.
    parent: dict[Cell, Cell] = {}      # parent[c] = cell from which c was discovered.
    expanded_count = 0

    while queue:
        cell = queue.popleft()
        expanded_count += 1
        discovered: list[Cell] = []
        for neighbor in grid.neighbors(cell):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            parent[neighbor] = cell
            queue.append(neighbor)
            discovered.append(neighbor)
            if neighbor == target:
                yield Expansion(cell, tuple(discovered))
                return SearchResult(reconstruct_path(parent, start, target), expanded_count, len(visited))
        yield Expansion(cell, tuple(discovered))

    return SearchResult(path=(), expanded_count=expanded_count, discovered_count=len(visited))


def bfs(grid: Grid) -> SearchResult:
    """Run BFS to completion without animation and return the result."""
    return run_to_completion(bfs_steps(grid))
