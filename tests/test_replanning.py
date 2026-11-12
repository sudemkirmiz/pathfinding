"""Hybrid sessions in the Pathfinder: phases, replanning, coalescing, pause, cancel."""

import unittest
from functools import partial
from unittest import mock

from algorithms.astar import astar
from algorithms.registry import Algorithm
from core.grid import Cell, Grid
from core.hybrid import HybridOutcome, HybridPhase, hybrid_steps, is_valid_route
from core.pathfinder import Pathfinder, SearchStatus
from tests.helpers import fake_planner, make_grid, reference_distance

SETTLE = 0.25           # Exact in binary floating point.
SPEEDS = (10,)
FINISHED = (SearchStatus.FOUND, SearchStatus.NO_PATH, SearchStatus.VERIFICATION_FAILED)


def hybrid_session(grid: Grid) -> Pathfinder:
    pathfinder = Pathfinder(grid, SPEEDS, 0, algorithm=Algorithm.HYBRID, replan_settle_seconds=SETTLE)
    pathfinder.toggle()
    return pathfinder


def run_plan(pathfinder: Pathfinder) -> None:
    """Step the active plan to the end (does not wait out a settle period)."""
    while pathfinder.status in (SearchStatus.RUNNING, SearchStatus.REPLANNING) and pathfinder.phase is not HybridPhase.SETTLING:
        pathfinder.step()


def settle_and_replan(pathfinder: Pathfinder) -> None:
    pathfinder.update(SETTLE)
    run_plan(pathfinder)


class HybridSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        # 7x9 grid; start left, target right, a vertical wall with a gap at the bottom.
        self.grid = make_grid(7, 9, Cell(3, 0), Cell(3, 8), [Cell(r, 4) for r in range(6)])

    def test_finds_verified_shortest_path(self) -> None:
        pathfinder = hybrid_session(self.grid)
        self.assertIs(pathfinder.status, SearchStatus.RUNNING)
        run_plan(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        hybrid = pathfinder.hybrid_result
        self.assertIs(hybrid.outcome, HybridOutcome.VERIFIED)
        self.assertEqual(hybrid.bfs.path_length, hybrid.astar.path_length)
        self.assertEqual(pathfinder.result.path_length, reference_distance(self.grid))
        self.assertEqual(pathfinder.path_cells, frozenset(hybrid.astar.path))
        self.assertEqual(pathfinder.phase_expanded_count(HybridPhase.BFS_CHECK), hybrid.bfs.expanded_count)
        self.assertEqual(pathfinder.phase_expanded_count(HybridPhase.ASTAR_PLAN), hybrid.astar.expanded_count)
        self.assertEqual(pathfinder.replan_count, 0)
        self.assertGreater(pathfinder.compute_seconds, 0.0)

    def test_phase_display_never_mixes_bfs_and_astar_exploration(self) -> None:
        pathfinder = hybrid_session(self.grid)
        pathfinder.step()
        self.assertIs(pathfinder.phase, HybridPhase.BFS_CHECK)
        while pathfinder.phase is HybridPhase.BFS_CHECK:
            pathfinder.step()
        self.assertIs(pathfinder.phase, HybridPhase.ASTAR_PLAN)
        self.assertEqual(set(pathfinder.expanded), set(), "A* phase starts with a clean view")
        self.assertEqual(set(pathfinder.frontier), {self.grid.start})
        self.assertIsNotNone(pathfinder.phase_expanded_count(HybridPhase.BFS_CHECK))

    def test_unreachable_target_gives_no_path(self) -> None:
        self.grid.add_wall(Cell(6, 4))
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.NO_PATH)
        self.assertEqual(pathfinder.path_cells, frozenset())
        self.assertIsNone(pathfinder.phase_expanded_count(HybridPhase.ASTAR_PLAN), "A* skipped")

    def test_edits_before_session_do_not_start_searches(self) -> None:
        pathfinder = Pathfinder(self.grid, SPEEDS, 0, algorithm=Algorithm.HYBRID, replan_settle_seconds=SETTLE)
        self.grid.add_wall(Cell(0, 0))
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.IDLE)
        self.assertIsNone(pathfinder.phase)

    def test_wall_on_route_hides_route_then_replans_around_it(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        old_route = pathfinder.result.path
        blocked = old_route[2]  # Not the single gap in the wall, so a detour exists.
        self.assertNotEqual(blocked, Cell(6, 4))
        self.grid.add_wall(blocked)

        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.REPLANNING)
        self.assertIs(pathfinder.phase, HybridPhase.SETTLING)
        self.assertEqual(pathfinder.path_cells, frozenset(), "old route must disappear immediately")
        self.assertIsNone(pathfinder.result)

        settle_and_replan(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        self.assertNotIn(blocked, pathfinder.path_cells)
        self.assertTrue(is_valid_route(self.grid, pathfinder.result.path))
        self.assertEqual(pathfinder.result.path_length, reference_distance(self.grid))
        self.assertEqual(pathfinder.replan_count, 1)

    def test_removing_wall_produces_shorter_route(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        detour_length = pathfinder.result.path_length
        self.grid.remove_wall(Cell(3, 4))  # Opens the direct row.
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.REPLANNING, "removal may shorten paths: replan")
        settle_and_replan(pathfinder)
        self.assertEqual(pathfinder.result.path_length, 8)
        self.assertLess(pathfinder.result.path_length, detour_length)

    def test_moving_start_and_target_replans_from_new_endpoints(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        self.grid.move_start(Cell(0, 0))
        self.grid.move_target(Cell(0, 8))
        settle_and_replan(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        self.assertEqual((pathfinder.result.path[0], pathfinder.result.path[-1]), (Cell(0, 0), Cell(0, 8)))
        self.assertEqual(pathfinder.result.path_length, reference_distance(self.grid))
        self.assertEqual(pathfinder.replan_count, 1, "both moves coalesced into one replan")

    def test_unrelated_wall_keeps_route_without_replanning(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        route = pathfinder.result
        self.grid.add_wall(Cell(0, 8))  # Far from the route along the bottom gap.
        self.assertNotIn(Cell(0, 8), route.path)
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        self.assertEqual(pathfinder.result, route)
        self.assertEqual((pathfinder.replan_count, pathfinder.routes_kept), (0, 1))
        self.assertEqual(route.path_length, reference_distance(self.grid), "kept route is still optimal")

    def test_no_path_kept_when_walls_are_only_added(self) -> None:
        self.grid.add_wall(Cell(6, 4))
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        self.grid.add_wall(Cell(0, 0))
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.NO_PATH)
        self.grid.remove_wall(Cell(6, 4))
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.REPLANNING)

    def test_rapid_edits_coalesce_into_one_replan_with_one_generator(self) -> None:
        pathfinder = hybrid_session(self.grid)
        for _ in range(5):
            pathfinder.step()
        first_generator = pathfinder._steps
        for col in range(5, 9):          # A burst of edits, each within the settle window.
            self.grid.add_wall(Cell(0, col))
            pathfinder.update(SETTLE / 5)
            self.assertIs(pathfinder.phase, HybridPhase.SETTLING)
            self.assertIsNone(pathfinder._steps, "no search may run while edits are still coming")
        self.assertIsNone(first_generator.gi_frame, "the outdated generator must be closed")
        self.assertEqual(pathfinder.replan_count, 0)

        settle_and_replan(pathfinder)
        self.assertEqual(pathfinder.replan_count, 1)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)

    def test_edit_during_plan_cancels_it_and_result_matches_latest_revision(self) -> None:
        pathfinder = hybrid_session(self.grid)
        for _ in range(10):
            pathfinder.step()
        self.grid.remove_wall(Cell(3, 4))
        self.grid.add_wall(Cell(3, 5))
        settle_and_replan(pathfinder)
        latest = hybrid_steps(self.grid.copy())
        while True:
            try:
                next(latest)
            except StopIteration as finished:
                expected = finished.value
                break
        self.assertEqual(pathfinder.hybrid_result, expected)
        self.assertEqual(pathfinder.result.path_length, astar(self.grid).path_length)

    def test_pause_freezes_replanning_and_resume_continues(self) -> None:
        pathfinder = hybrid_session(self.grid)
        pathfinder.step()
        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.PAUSED)

        self.grid.add_wall(Cell(6, 0))   # Edit while paused.
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.PAUSED, "a paused session stays paused")
        self.assertIs(pathfinder.phase, HybridPhase.SETTLING)
        self.assertEqual(pathfinder.expanded_count, 0, "outdated exploration is hidden")
        self.assertEqual(pathfinder.replan_count, 0, "no replan while paused")

        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.REPLANNING)
        settle_and_replan(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        self.assertEqual(pathfinder.replan_count, 1)

    def test_pause_and_resume_during_planning(self) -> None:
        pathfinder = hybrid_session(self.grid)
        pathfinder.update(0.5)  # 5 steps at 10 steps/s.
        progress = pathfinder.expanded_count
        pathfinder.toggle()
        pathfinder.update(0.25)
        self.assertEqual(pathfinder.expanded_count, progress)
        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.RUNNING)
        pathfinder.update(0.1)
        self.assertEqual(pathfinder.expanded_count, progress + 1)

    def test_switching_algorithm_ends_session(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        self.grid.add_wall(pathfinder.result.path[2])
        pathfinder.update(SETTLE)          # Replan starts...
        pathfinder.step()
        pathfinder.step()                  # ...and is mid-way through the BFS check.
        replan_generator = pathfinder._steps
        self.assertIsNotNone(replan_generator)
        pathfinder.select(Algorithm.ASTAR)
        self.assertIs(pathfinder.status, SearchStatus.IDLE)
        self.assertIsNone(pathfinder.phase)
        self.assertEqual(pathfinder.replan_count, 0)
        self.assertIsNone(replan_generator.gi_frame, "the hybrid generator must be closed")
        self.grid.add_wall(Cell(0, 0))
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.IDLE, "plain A* does not auto-replan")

    def test_clear_ends_session_and_grid_reset_replans(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        self.grid.reset()                # 'R': a map edit like any other.
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.REPLANNING)
        settle_and_replan(pathfinder)
        self.assertEqual(pathfinder.result.path_length, 8)

        pathfinder.clear()               # 'X': ends the session.
        self.assertIs(pathfinder.status, SearchStatus.IDLE)
        self.assertEqual((pathfinder.replan_count, pathfinder.path_cells), (0, frozenset()))
        self.grid.add_wall(Cell(0, 0))
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.IDLE)

    def test_comparison_invalidated_by_edit_in_hybrid_mode(self) -> None:
        pathfinder = hybrid_session(self.grid)
        run_plan(pathfinder)
        pathfinder.compare(repetitions=1, warmup_runs=0)
        self.assertEqual([e.algorithm for e in pathfinder.comparison.entries], [Algorithm.BFS, Algorithm.ASTAR])
        self.grid.add_wall(Cell(0, 8))
        self.assertIsNone(pathfinder.comparison)

    def test_verification_failure_is_reported_without_a_route(self) -> None:
        wrong = (self.grid.start, self.grid.target)  # Teleports: invalid.
        faulty = partial(hybrid_steps, planner=fake_planner(wrong))
        with mock.patch("core.pathfinder.hybrid_steps", faulty):
            pathfinder = hybrid_session(self.grid)
            run_plan(pathfinder)
            self.assertIs(pathfinder.status, SearchStatus.VERIFICATION_FAILED)
            self.assertIsNone(pathfinder.result)
            self.assertEqual(pathfinder.path_cells, frozenset())
            self.grid.add_wall(Cell(0, 0))
            pathfinder.update(0.0)
            self.assertIs(pathfinder.status, SearchStatus.REPLANNING, "a failed plan is retried on edit")


if __name__ == "__main__":
    unittest.main()
