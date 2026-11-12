import random
import unittest

from algorithms.astar import astar, astar_steps, manhattan_distance
from algorithms.bfs import bfs
from core.grid import Cell
from tests.helpers import assert_valid_path, collect, make_grid, random_grid, reference_distance

# Seeds whose random grid (max_size=12) makes A* improve an open cell's g,
# i.e. leaves stale heap entries behind. Found by scanning seeds 0..499.
IMPROVING_SEEDS = (91, 134, 169, 174, 177)


class AStarTests(unittest.TestCase):
    def test_optimal_path_on_empty_grid(self) -> None:
        grid = make_grid(20, 50, Cell(10, 10), Cell(3, 40))
        result = astar(grid)
        self.assertEqual(result.path_length, 7 + 30)
        assert_valid_path(self, grid, result.path)

    def test_heuristic_focuses_search_on_empty_grid(self) -> None:
        """With no walls, Manhattan h is exact: only cells on one optimal path are expanded."""
        grid = make_grid(20, 50, Cell(10, 10), Cell(10, 39))
        result = astar(grid)
        self.assertEqual(result.expanded_count, result.path_length)
        self.assertLess(result.expanded_count, bfs(grid).expanded_count)

    def test_routes_around_obstacles(self) -> None:
        walls = [Cell(r, 2) for r in range(4)]
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), walls)
        result = astar(grid)
        self.assertEqual(result.path_length, 12)
        assert_valid_path(self, grid, result.path)

    def test_reports_unreachable_target(self) -> None:
        walls = [Cell(r, 2) for r in range(5)]
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), walls)
        result = astar(grid)
        self.assertFalse(result.found)
        self.assertIsNone(result.path_length)
        self.assertEqual((result.expanded_count, result.discovered_count), (10, 10))

    def test_adjacent_endpoints_and_boundaries(self) -> None:
        self.assertEqual(astar(make_grid(3, 3, Cell(2, 2), Cell(2, 1))).path, (Cell(2, 2), Cell(2, 1)))
        self.assertEqual(astar(make_grid(1, 4, Cell(0, 3), Cell(0, 0))).path_length, 3)
        self.assertEqual(astar(make_grid(4, 1, Cell(0, 0), Cell(3, 0))).path_length, 3)

    def test_never_expands_or_discovers_walls(self) -> None:
        rng = random.Random(11)
        walls = [Cell(r, c) for r in range(15) for c in range(15) if rng.random() < 0.3]
        grid = make_grid(15, 15, Cell(0, 0), Cell(14, 14), walls)
        events, result = collect(grid, astar_steps)
        for event in events:
            for cell in (event.cell, *event.discovered, *event.improved):
                self.assertFalse(grid.is_wall(cell))
        if result.found:
            assert_valid_path(self, grid, result.path)

    def test_stale_heap_entries_are_skipped(self) -> None:
        for seed in IMPROVING_SEEDS:
            grid = random_grid(seed, max_size=12)
            events, result = collect(grid, astar_steps)
            with self.subTest(seed=seed):
                self.assertTrue(any(event.improved for event in events), "seed must exercise improvement")
                expanded = [event.cell for event in events]
                self.assertEqual(len(expanded), len(set(expanded)), "a cell was expanded twice")
                discovered = {grid.start}
                for event in events:
                    for cell in event.improved:
                        self.assertIn(cell, discovered, "improved cell must already be discovered")
                        self.assertNotIn(cell, expanded[: expanded.index(event.cell)], "closed cell improved")
                    discovered.update(event.discovered)
                self.assertEqual(result.path_length, reference_distance(grid))

    def test_unique_expansions_and_discoveries_on_random_grids(self) -> None:
        for seed in range(150):
            grid = random_grid(seed, max_size=12)
            events, result = collect(grid, astar_steps)
            with self.subTest(seed=seed):
                expanded = [event.cell for event in events]
                discovered = [grid.start] + [cell for event in events for cell in event.discovered]
                self.assertEqual(len(expanded), len(set(expanded)))
                self.assertEqual(len(discovered), len(set(discovered)))
                self.assertEqual(result.expanded_count, len(expanded))
                self.assertEqual(result.discovered_count, len(discovered))
                self.assertNotIn(grid.target, expanded, "target is discovered, never expanded")

    def test_expansion_f_values_never_decrease(self) -> None:
        """Consistent heuristic: cells are expanded in non-decreasing f = g + h."""
        grid = random_grid(174, max_size=12)
        events, _ = collect(grid, astar_steps)
        g = {grid.start: 0}
        f_values = []
        for event in events:
            f_values.append(g[event.cell] + manhattan_distance(event.cell, grid.target))
            for cell in (*event.discovered, *event.improved):
                g[cell] = g[event.cell] + 1
        self.assertEqual(f_values, sorted(f_values))

    def test_deterministic_tie_breaking(self) -> None:
        grid = make_grid(5, 5, Cell(4, 0), Cell(0, 4))
        events, first = collect(grid, astar_steps)
        _, second = collect(grid, astar_steps)
        self.assertEqual(first, second)
        # Every move toward the target ties on f and h; insertion order (up before
        # right) decides, so the path goes straight up and then right.
        self.assertEqual(
            first.path,
            (Cell(4, 0), Cell(3, 0), Cell(2, 0), Cell(1, 0), Cell(0, 0), Cell(0, 1), Cell(0, 2), Cell(0, 3), Cell(0, 4)),
        )
        self.assertEqual(events[0].discovered, (Cell(3, 0), Cell(4, 1)))

    def test_matches_bfs_and_reference_on_random_grids(self) -> None:
        for seed in range(300):
            grid = random_grid(seed, max_size=12)
            with self.subTest(seed=seed):
                a_star, breadth_first = astar(grid), bfs(grid)
                self.assertEqual(a_star.path_length, breadth_first.path_length)
                self.assertEqual(a_star.path_length, reference_distance(grid))
                if a_star.found:
                    assert_valid_path(self, grid, a_star.path)


if __name__ == "__main__":
    unittest.main()
