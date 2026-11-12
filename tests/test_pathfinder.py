import random
import unittest

from algorithms.astar import astar
from algorithms.bfs import bfs
from algorithms.registry import Algorithm
from core.grid import Cell, Grid
from core.pathfinder import MAX_FRAME_SECONDS, Pathfinder, SearchStatus
from tests.helpers import reference_distance

SPEEDS = (10, 100)


def make_pathfinder(walls: tuple[Cell, ...] = ()) -> tuple[Grid, Pathfinder]:
    grid = Grid(6, 8, Cell(0, 0), Cell(5, 7))
    for wall in walls:
        grid.add_wall(wall)
    return grid, Pathfinder(grid, SPEEDS, speed_index=0)


def run_to_end(pathfinder: Pathfinder) -> None:
    while pathfinder.status in (SearchStatus.RUNNING, SearchStatus.PAUSED):
        pathfinder.step()


class PathfinderTests(unittest.TestCase):
    def test_initial_state_is_idle_and_empty(self) -> None:
        _, pathfinder = make_pathfinder()
        self.assertIs(pathfinder.status, SearchStatus.IDLE)
        self.assertEqual((pathfinder.expanded_count, pathfinder.discovered_count), (0, 0))
        pathfinder.update(1.0)
        self.assertIs(pathfinder.status, SearchStatus.IDLE, "update must not start a search")

    def test_start_pause_resume(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.RUNNING)
        pathfinder.update(0.2)  # 10 steps/s * 0.2 s = 2 steps
        self.assertEqual(pathfinder.expanded_count, 2)

        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.PAUSED)
        pathfinder.update(MAX_FRAME_SECONDS)
        self.assertEqual(pathfinder.expanded_count, 2, "paused search must not advance")

        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.RUNNING)
        pathfinder.update(0.1)
        self.assertEqual(pathfinder.expanded_count, 3)

    def test_fractional_frames_accumulate(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        # 0.0625 s is exact in binary floating point: 0.625 steps per frame.
        for _ in range(8):
            pathfinder.update(0.0625)
        self.assertEqual(pathfinder.expanded_count, 5)

    def test_long_frame_is_capped(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        pathfinder.update(60.0)
        self.assertEqual(pathfinder.expanded_count, int(MAX_FRAME_SECONDS * SPEEDS[0]))

    def test_finishes_with_same_result_as_direct_bfs(self) -> None:
        grid, pathfinder = make_pathfinder(walls=(Cell(1, 0), Cell(1, 1), Cell(1, 2)))
        pathfinder.toggle()
        run_to_end(pathfinder)
        expected = bfs(grid)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)
        self.assertEqual(pathfinder.result, expected)
        self.assertEqual(pathfinder.path_cells, frozenset(expected.path))
        self.assertEqual(pathfinder.expanded_count, expected.expanded_count)
        self.assertEqual(pathfinder.discovered_count, expected.discovered_count)
        self.assertIsNone(pathfinder.current)
        self.assertGreater(pathfinder.compute_seconds, 0.0)

    def test_visual_state_tracks_real_bfs_events(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        pathfinder.step()
        # First expansion of (0,0): down (1,0) and right (0,1) are discovered.
        self.assertEqual(pathfinder.current, Cell(0, 0))
        self.assertEqual(set(pathfinder.expanded), {Cell(0, 0)})
        self.assertEqual(set(pathfinder.frontier), {Cell(1, 0), Cell(0, 1)})

    def test_no_path_state(self) -> None:
        _, pathfinder = make_pathfinder(walls=tuple(Cell(r, 3) for r in range(6)))
        pathfinder.toggle()
        run_to_end(pathfinder)
        self.assertIs(pathfinder.status, SearchStatus.NO_PATH)
        self.assertEqual(pathfinder.path_cells, frozenset())
        self.assertIsNone(pathfinder.result.path_length)

    def test_clear_preserves_walls_and_endpoints(self) -> None:
        walls = (Cell(2, 2), Cell(2, 3))
        grid, pathfinder = make_pathfinder(walls)
        pathfinder.toggle()
        run_to_end(pathfinder)
        pathfinder.clear()
        self.assertIs(pathfinder.status, SearchStatus.IDLE)
        self.assertEqual((len(pathfinder.expanded), len(pathfinder.frontier), len(pathfinder.path_cells)), (0, 0, 0))
        self.assertTrue(all(grid.is_wall(wall) for wall in walls))
        self.assertEqual((grid.start, grid.target), (Cell(0, 0), Cell(5, 7)))

    def test_toggle_after_finish_starts_fresh_search(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        run_to_end(pathfinder)
        pathfinder.toggle()
        self.assertIs(pathfinder.status, SearchStatus.RUNNING)
        self.assertIsNone(pathfinder.result)
        self.assertEqual(pathfinder.expanded_count, 0)

    def test_grid_edit_invalidates_running_paused_and_finished_searches(self) -> None:
        edits = (
            lambda g: g.add_wall(Cell(3, 3)),
            lambda g: g.move_start(Cell(0, 1)),
            lambda g: g.move_target(Cell(5, 6)),
            lambda g: g.clear_walls(),
            lambda g: g.reset(),
        )
        for edit in edits:
            for finish, pause in ((False, False), (False, True), (True, False)):
                grid, pathfinder = make_pathfinder(walls=(Cell(4, 4),))
                pathfinder.toggle()
                pathfinder.step()
                if pause:
                    pathfinder.toggle()
                if finish:
                    run_to_end(pathfinder)
                with self.subTest(edit=edit, finish=finish, pause=pause):
                    edit(grid)
                    pathfinder.update(0.0)
                    self.assertIs(pathfinder.status, SearchStatus.IDLE)
                    self.assertEqual(pathfinder.path_cells, frozenset())
                    self.assertEqual(pathfinder.expanded_count, 0)

    def test_new_search_uses_updated_grid(self) -> None:
        grid, pathfinder = make_pathfinder()
        pathfinder.toggle()
        run_to_end(pathfinder)
        old_length = pathfinder.result.path_length
        for row in range(5):
            grid.add_wall(Cell(row, 4))  # Force a detour through the bottom row.
        pathfinder.toggle()
        run_to_end(pathfinder)
        self.assertEqual(pathfinder.result, bfs(grid))
        self.assertGreaterEqual(pathfinder.result.path_length, old_length)
        self.assertTrue(pathfinder.path_cells.isdisjoint({Cell(r, 4) for r in range(5)}))

    def test_no_op_edit_keeps_result(self) -> None:
        grid, pathfinder = make_pathfinder(walls=(Cell(3, 3),))
        pathfinder.toggle()
        run_to_end(pathfinder)
        grid.add_wall(Cell(3, 3))        # Already a wall.
        grid.remove_wall(Cell(0, 5))     # Not a wall.
        grid.move_start(grid.start)      # Same cell.
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)

    def test_speed_levels_are_clamped(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.slower()
        self.assertEqual(pathfinder.steps_per_second, SPEEDS[0])
        for _ in range(5):
            pathfinder.faster()
        self.assertEqual(pathfinder.steps_per_second, SPEEDS[-1])

    def test_rejects_invalid_speed_index(self) -> None:
        grid = Grid(2, 2, Cell(0, 0), Cell(1, 1))
        with self.assertRaises(ValueError):
            Pathfinder(grid, SPEEDS, speed_index=len(SPEEDS))
        with self.assertRaises(ValueError):
            Pathfinder(grid, (), speed_index=0)



class AlgorithmSelectionTests(unittest.TestCase):
    def test_default_is_bfs_and_astar_runs_through_same_pipeline(self) -> None:
        grid, pathfinder = make_pathfinder(walls=(Cell(2, 1), Cell(2, 2), Cell(2, 3), Cell(2, 4)))
        self.assertIs(pathfinder.algorithm, Algorithm.BFS)
        pathfinder.select(Algorithm.ASTAR)
        pathfinder.toggle()
        pathfinder.step()
        self.assertEqual(pathfinder.current, grid.start)
        run_to_end(pathfinder)
        expected = astar(grid)
        self.assertEqual(pathfinder.result, expected)
        self.assertEqual(pathfinder.expanded_count, expected.expanded_count)
        self.assertEqual(pathfinder.discovered_count, expected.discovered_count)

    def test_switching_algorithm_discards_search_in_every_state(self) -> None:
        for finish, pause in ((False, False), (False, True), (True, False)):
            _, pathfinder = make_pathfinder()
            pathfinder.toggle()
            pathfinder.step()
            if pause:
                pathfinder.toggle()
            if finish:
                run_to_end(pathfinder)
            with self.subTest(finish=finish, pause=pause):
                pathfinder.select(Algorithm.ASTAR)
                self.assertIs(pathfinder.algorithm, Algorithm.ASTAR)
                self.assertIs(pathfinder.status, SearchStatus.IDLE, "must not auto-start")
                self.assertEqual((pathfinder.expanded_count, pathfinder.discovered_count), (0, 0))
                self.assertEqual(pathfinder.path_cells, frozenset())
                self.assertIsNone(pathfinder.result)

    def test_selecting_same_algorithm_keeps_result(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        run_to_end(pathfinder)
        pathfinder.select(Algorithm.BFS)
        self.assertIs(pathfinder.status, SearchStatus.FOUND)

    def test_astar_paused_search_is_invalidated_by_edit(self) -> None:
        grid, pathfinder = make_pathfinder()
        pathfinder.select(Algorithm.ASTAR)
        pathfinder.toggle()
        pathfinder.step()
        pathfinder.toggle()
        grid.add_wall(Cell(3, 3))
        pathfinder.update(0.0)
        self.assertIs(pathfinder.status, SearchStatus.IDLE)


class ComparisonStateTests(unittest.TestCase):
    def test_compare_does_not_disturb_animated_search(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.toggle()
        pathfinder.step()
        pathfinder.step()

        def snapshot() -> tuple:
            return (pathfinder.status, pathfinder.current, set(pathfinder.expanded),
                    set(pathfinder.frontier), pathfinder.compute_seconds, pathfinder.algorithm)

        before = snapshot()
        pathfinder.compare(repetitions=2, warmup_runs=1)
        self.assertEqual(snapshot(), before)
        self.assertIsNotNone(pathfinder.comparison)

    def test_grid_edit_invalidates_comparison(self) -> None:
        grid, pathfinder = make_pathfinder()
        pathfinder.compare(repetitions=1, warmup_runs=0)
        grid.add_wall(Cell(3, 3))
        self.assertIsNone(pathfinder.comparison, "stale report must never be visible")
        grid.remove_wall(Cell(3, 3))
        self.assertIsNone(pathfinder.comparison, "revision moved on; old report stays invalid")

    def test_clear_start_and_hide_close_comparison_but_selection_keeps_it(self) -> None:
        _, pathfinder = make_pathfinder()
        pathfinder.compare(repetitions=1, warmup_runs=0)
        pathfinder.select(Algorithm.ASTAR)
        self.assertIsNotNone(pathfinder.comparison, "comparison covers both algorithms")
        pathfinder.hide_comparison()
        self.assertIsNone(pathfinder.comparison)

        pathfinder.compare(repetitions=1, warmup_runs=0)
        pathfinder.clear()
        self.assertIsNone(pathfinder.comparison)

        pathfinder.compare(repetitions=1, warmup_runs=0)
        pathfinder.toggle()
        self.assertIsNone(pathfinder.comparison, "starting an animation hides the overlay")


class RepeatedSearchTests(unittest.TestCase):
    def test_repeated_searches_across_modes_and_edits_never_reuse_stale_state(self) -> None:
        rng = random.Random(42)
        grid = Grid(8, 12, Cell(0, 0), Cell(7, 11))
        pathfinder = Pathfinder(grid, SPEEDS, 0)
        modes = (Algorithm.BFS, Algorithm.ASTAR, Algorithm.HYBRID)
        for round_index in range(30):
            for _ in range(rng.randint(1, 6)):      # Random edits between searches.
                cell = Cell(rng.randrange(8), rng.randrange(12))
                if rng.random() < 0.7:
                    grid.add_wall(cell)
                else:
                    grid.remove_wall(cell)
            pathfinder.select(modes[round_index % len(modes)])
            pathfinder.update(0.0)
            pathfinder.toggle()
            while pathfinder.status in (SearchStatus.RUNNING, SearchStatus.REPLANNING):
                pathfinder.step()
            with self.subTest(round=round_index, mode=pathfinder.algorithm):
                expected = reference_distance(grid)
                self.assertIs(pathfinder.status, SearchStatus.FOUND if expected is not None else SearchStatus.NO_PATH)
                self.assertEqual(pathfinder.result.path_length, expected)
                self.assertTrue(pathfinder.path_cells.isdisjoint(grid.walls))
                if expected is not None:
                    self.assertEqual((pathfinder.result.path[0], pathfinder.result.path[-1]), (grid.start, grid.target))

if __name__ == "__main__":
    unittest.main()
