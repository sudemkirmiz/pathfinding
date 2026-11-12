"""Tests for the hybrid search generator and its verification rules (core.hybrid)."""

import random
import unittest

from algorithms.astar import astar
from algorithms.bfs import bfs
from algorithms.common import run_to_completion
from core.grid import Cell
from core.hybrid import (
    HybridOutcome,
    HybridPhase,
    PhaseStarted,
    edit_preserves_result,
    hybrid_steps,
    is_valid_route,
)
from tests.helpers import assert_valid_path, fake_planner, make_grid, random_grid, reference_distance


class HybridStepsTests(unittest.TestCase):
    def test_verified_route_is_the_astar_route_and_shortest(self) -> None:
        grid = make_grid(10, 20, Cell(5, 2), Cell(5, 17), [Cell(r, 10) for r in range(1, 10)])
        result = run_to_completion(hybrid_steps(grid))
        self.assertIs(result.outcome, HybridOutcome.VERIFIED)
        self.assertEqual(result.bfs, bfs(grid))
        self.assertEqual(result.astar, astar(grid))
        self.assertIs(result.route, result.astar)
        self.assertEqual(result.route.path_length, reference_distance(grid))
        assert_valid_path(self, grid, result.route.path)

    def test_phases_run_in_order_bfs_then_astar(self) -> None:
        grid = make_grid(4, 4, Cell(0, 0), Cell(3, 3))
        markers = [event.phase for event in hybrid_steps(grid) if isinstance(event, PhaseStarted)]
        self.assertEqual(markers, [HybridPhase.BFS_CHECK, HybridPhase.ASTAR_PLAN])

    def test_unreachable_target_skips_astar(self) -> None:
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), [Cell(r, 2) for r in range(5)])
        steps = hybrid_steps(grid)
        events = []
        while True:
            try:
                events.append(next(steps))
            except StopIteration as finished:
                result = finished.value
                break
        self.assertIs(result.outcome, HybridOutcome.NO_PATH)
        self.assertIsNone(result.astar)
        self.assertEqual(result.route.path, ())
        self.assertNotIn(PhaseStarted(HybridPhase.ASTAR_PLAN), events)

    def test_bfs_and_astar_agree_on_random_grids(self) -> None:
        for seed in range(200):
            grid = random_grid(seed, max_size=12)
            with self.subTest(seed=seed):
                result = run_to_completion(hybrid_steps(grid))
                self.assertIn(result.outcome, (HybridOutcome.VERIFIED, HybridOutcome.NO_PATH))
                self.assertEqual(result.route.path_length, reference_distance(grid))

    def test_longer_planner_route_is_rejected(self) -> None:
        grid = make_grid(3, 3, Cell(0, 0), Cell(0, 2))
        detour = (Cell(0, 0), Cell(1, 0), Cell(1, 1), Cell(1, 2), Cell(0, 2))  # valid but 4 > 2 moves
        result = run_to_completion(hybrid_steps(grid, planner=fake_planner(detour)))
        self.assertIs(result.outcome, HybridOutcome.VERIFICATION_FAILED)
        self.assertIsNone(result.route)

    def test_route_through_wall_is_rejected_even_with_matching_length(self) -> None:
        grid = make_grid(3, 3, Cell(0, 0), Cell(0, 2), [Cell(0, 1)])
        self.assertEqual(bfs(grid).path_length, 4)
        through_wall = (Cell(0, 0), Cell(1, 0), Cell(1, 1), Cell(0, 1), Cell(0, 2))  # 4 moves, crosses wall
        result = run_to_completion(hybrid_steps(grid, planner=fake_planner(through_wall)))
        self.assertIs(result.outcome, HybridOutcome.VERIFICATION_FAILED)

    def test_is_valid_route(self) -> None:
        grid = make_grid(3, 3, Cell(0, 0), Cell(0, 2), [Cell(1, 1)])
        self.assertTrue(is_valid_route(grid, (Cell(0, 0), Cell(0, 1), Cell(0, 2))))
        self.assertFalse(is_valid_route(grid, ()))
        self.assertFalse(is_valid_route(grid, (Cell(0, 0), Cell(0, 2))), "jump")
        self.assertFalse(is_valid_route(grid, (Cell(0, 1), Cell(0, 2))), "wrong start")
        self.assertFalse(is_valid_route(grid, (Cell(0, 0), Cell(1, 0), Cell(1, 1), Cell(1, 2), Cell(0, 2))), "wall")


class EditPreservesResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), [Cell(3, 3)])
        self.route = astar(self.grid).path  # Along row 0.
        self.planned_on = self.grid.copy()

    def test_wall_added_off_route_keeps_result(self) -> None:
        self.grid.add_wall(Cell(4, 0))
        self.assertTrue(edit_preserves_result(self.planned_on, self.grid, self.route))

    def test_wall_added_on_route_invalidates(self) -> None:
        self.grid.add_wall(Cell(0, 2))
        self.assertFalse(edit_preserves_result(self.planned_on, self.grid, self.route))

    def test_wall_removed_invalidates_even_off_route(self) -> None:
        self.grid.remove_wall(Cell(3, 3))
        self.assertFalse(edit_preserves_result(self.planned_on, self.grid, self.route))

    def test_endpoint_moved_invalidates(self) -> None:
        self.grid.move_target(Cell(4, 4))
        self.assertFalse(edit_preserves_result(self.planned_on, self.grid, self.route))

    def test_no_path_result_survives_added_walls(self) -> None:
        grid = make_grid(5, 5, Cell(0, 0), Cell(0, 4), [Cell(r, 2) for r in range(5)])
        planned_on = grid.copy()
        grid.add_wall(Cell(4, 4))
        self.assertTrue(edit_preserves_result(planned_on, grid, ()))
        self.assertIsNone(bfs(grid).path_length, "adding walls cannot make the target reachable")



class FullSizeDenseMapTests(unittest.TestCase):
    """BFS, A* and the hybrid agree on full 20x50 maps with dense random obstacles."""

    def test_agreement_on_dense_full_size_maps(self) -> None:
        for seed in range(12):
            rng = random.Random(1000 + seed)
            cells = [Cell(r, c) for r in range(20) for c in range(50)]
            start, target = rng.sample(cells, 2)
            density = 0.25 + 0.03 * seed   # 25% .. 58% walls
            grid = make_grid(20, 50, start, target, [cell for cell in cells if rng.random() < density])
            with self.subTest(seed=seed, density=round(density, 2)):
                expected = reference_distance(grid)
                breadth_first, a_star = bfs(grid), astar(grid)
                hybrid = run_to_completion(hybrid_steps(grid))
                self.assertEqual(breadth_first.path_length, expected)
                self.assertEqual(a_star.path_length, expected)
                self.assertEqual(hybrid.route.path_length, expected)
                self.assertIs(hybrid.outcome, HybridOutcome.VERIFIED if expected is not None else HybridOutcome.NO_PATH)
                if expected is not None:
                    assert_valid_path(self, grid, a_star.path)

if __name__ == "__main__":
    unittest.main()
