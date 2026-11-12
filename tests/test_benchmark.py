import unittest

from algorithms.astar import astar
from algorithms.bfs import bfs
from algorithms.registry import Algorithm
from core.benchmark import compare_algorithms
from core.grid import Cell
from tests.helpers import make_grid, random_grid


class CompareAlgorithmsTests(unittest.TestCase):
    def test_reports_every_algorithm_with_exact_counts(self) -> None:
        grid = make_grid(10, 20, Cell(5, 2), Cell(5, 17), [Cell(r, 10) for r in range(1, 10)])
        report = compare_algorithms(grid, repetitions=3, warmup_runs=1)
        self.assertEqual([entry.algorithm for entry in report.entries], [Algorithm.BFS, Algorithm.ASTAR])
        by_algorithm = {entry.algorithm: entry for entry in report.entries}
        self.assertEqual(by_algorithm[Algorithm.BFS].result, bfs(grid))
        self.assertEqual(by_algorithm[Algorithm.ASTAR].result, astar(grid))
        for entry in report.entries:
            self.assertGreater(entry.median_seconds, 0.0)
        self.assertEqual((report.repetitions, report.warmup_runs, report.revision), (3, 1, grid.revision))

    def test_metric_definitions_are_consistent_on_random_grids(self) -> None:
        for seed in range(60):
            grid = random_grid(seed, max_size=12)
            report = compare_algorithms(grid, repetitions=1, warmup_runs=0)
            bfs_result, astar_result = (entry.result for entry in report.entries)
            with self.subTest(seed=seed):
                self.assertEqual(bfs_result.path_length, astar_result.path_length)
                for result in (bfs_result, astar_result):
                    # Expanded cells are a subset of discovered cells; the start counts as discovered.
                    self.assertLessEqual(result.expanded_count, result.discovered_count)
                    self.assertGreaterEqual(result.discovered_count, 1)
                    if result.found:
                        self.assertEqual(result.path_length, len(result.path) - 1)

    def test_runs_on_snapshot_and_leaves_grid_untouched(self) -> None:
        grid = make_grid(6, 6, Cell(0, 0), Cell(5, 5), [Cell(2, 2)])
        revision = grid.revision
        compare_algorithms(grid, repetitions=2, warmup_runs=1)
        self.assertEqual(grid.revision, revision)
        self.assertEqual(grid.wall_count, 1)

    def test_rejects_invalid_repetitions(self) -> None:
        grid = make_grid(2, 2, Cell(0, 0), Cell(1, 1))
        with self.assertRaises(ValueError):
            compare_algorithms(grid, repetitions=0, warmup_runs=0)
        with self.assertRaises(ValueError):
            compare_algorithms(grid, repetitions=1, warmup_runs=-1)


if __name__ == "__main__":
    unittest.main()
