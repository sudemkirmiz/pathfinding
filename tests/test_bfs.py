import random
import unittest

from algorithms.bfs import bfs, bfs_steps
from algorithms.common import Expansion
from core.grid import Cell
from tests.helpers import assert_valid_path, collect, make_grid, random_grid, reference_distance


class BfsTests(unittest.TestCase):
    def test_shortest_path_on_empty_grid_is_manhattan_distance(self) -> None:
        grid = make_grid(20, 50, Cell(10, 10), Cell(3, 40))
        result = bfs(grid)
        self.assertTrue(result.found)
        self.assertEqual(result.path_length, 7 + 30)
        assert_valid_path(self, grid, result.path)

    def test_routes_around_obstacles(self) -> None:
        # Vertical wall in column 2 with a single gap at the bottom row.
        walls = [Cell(r, 2) for r in range(4)]
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), walls)
        result = bfs(grid)
        self.assertEqual(result.path_length, 4 + 4 + 4)
        assert_valid_path(self, grid, result.path)
        self.assertIn(Cell(4, 2), result.path)

    def test_reports_unreachable_target(self) -> None:
        walls = [Cell(r, 2) for r in range(5)]
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), walls)
        result = bfs(grid)
        self.assertFalse(result.found)
        self.assertEqual(result.path, ())
        self.assertIsNone(result.path_length)
        self.assertEqual(result.expanded_count, 10, "the whole reachable region (cols 0-1) is explored")

    def test_fully_enclosed_start(self) -> None:
        start = Cell(2, 2)
        walls = [Cell(1, 2), Cell(3, 2), Cell(2, 1), Cell(2, 3)]
        result = bfs(make_grid(5, 5, start, Cell(0, 0), walls))
        self.assertFalse(result.found)
        self.assertEqual((result.expanded_count, result.discovered_count), (1, 1))

    def test_adjacent_start_and_target(self) -> None:
        grid = make_grid(3, 3, Cell(1, 1), Cell(1, 2))
        result = bfs(grid)
        self.assertEqual(result.path, (Cell(1, 1), Cell(1, 2)))
        self.assertEqual(result.path_length, 1)

    def test_corner_endpoints_and_single_row_grid(self) -> None:
        grid = make_grid(1, 6, Cell(0, 0), Cell(0, 5))
        self.assertEqual(bfs(grid).path, tuple(Cell(0, c) for c in range(6)))

    def test_never_expands_or_discovers_walls(self) -> None:
        rng = random.Random(7)
        walls = [Cell(r, c) for r in range(15) for c in range(15) if rng.random() < 0.3]
        grid = make_grid(15, 15, Cell(0, 0), Cell(14, 14), walls)
        events, _ = collect(grid, bfs_steps)
        for event in events:
            self.assertFalse(grid.is_wall(event.cell))
            for cell in event.discovered:
                self.assertFalse(grid.is_wall(cell))

    def test_each_cell_discovered_and_expanded_at_most_once(self) -> None:
        grid = make_grid(10, 10, Cell(0, 0), Cell(9, 9), [Cell(5, c) for c in range(9)])
        events, result = collect(grid, bfs_steps)
        discovered = [grid.start] + [cell for event in events for cell in event.discovered]
        expanded = [event.cell for event in events]
        self.assertEqual(len(discovered), len(set(discovered)))
        self.assertEqual(len(expanded), len(set(expanded)))
        self.assertEqual(result.discovered_count, len(discovered))
        self.assertEqual(result.expanded_count, len(expanded))

    def test_expansions_follow_fifo_order(self) -> None:
        """Cells must be expanded in exactly the order they were discovered."""
        grid = make_grid(8, 8, Cell(0, 0), Cell(7, 7), [Cell(3, c) for c in range(1, 8)])
        events, _ = collect(grid, bfs_steps)
        discovery_order = [grid.start] + [cell for event in events for cell in event.discovered]
        expansion_order = [event.cell for event in events]
        self.assertEqual(expansion_order, discovery_order[: len(expansion_order)])

    def test_deterministic_neighbor_order(self) -> None:
        grid = make_grid(5, 5, Cell(2, 2), Cell(0, 0))
        events, first = collect(grid, bfs_steps)
        # Up, down, left, right.
        self.assertEqual(events[0], Expansion(Cell(2, 2), (Cell(1, 2), Cell(3, 2), Cell(2, 1), Cell(2, 3))))
        _, second = collect(grid, bfs_steps)
        self.assertEqual(first, second)
        # With "up" tried first, the path goes up before going left.
        self.assertEqual(first.path, (Cell(2, 2), Cell(1, 2), Cell(0, 2), Cell(0, 1), Cell(0, 0)))

    def test_matches_reference_on_random_grids(self) -> None:
        for seed in range(200):
            grid = random_grid(seed)
            with self.subTest(seed=seed):
                result = bfs(grid)
                self.assertEqual(result.path_length, reference_distance(grid))
                if result.found:
                    assert_valid_path(self, grid, result.path)

if __name__ == "__main__":
    unittest.main()
