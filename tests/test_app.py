"""Input-handling tests that drive ``App`` with synthetic Pygame events.

They run headless through SDL's dummy video driver, so they verify the event
logic and rendering calls but not physical mouse hardware.
"""

import os
import time
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import config  # noqa: E402
from algorithms.registry import Algorithm  # noqa: E402
from core.grid import Cell  # noqa: E402
from core.pathfinder import SearchStatus  # noqa: E402
from core.hybrid import HybridPhase  # noqa: E402
from ui import theme  # noqa: E402
from ui import content  # noqa: E402
from ui.content import STATUS_LABEL, SUBTITLE  # noqa: E402
from ui.controls import (  # noqa: E402
    BUTTON_LABELS,
    HYBRID_FOUND_TEXT,
    HYBRID_PHASE_TEXT,
    MODE_BUTTONS,
    PAUSED_REPLAN_TEXT,
    START_LABELS,
    STATUS_TEXT,
    Button,
    status_text,
    is_button_active,
    is_button_enabled,
    start_button_label,
)
from main import App, DragMode, LEFT_MOUSE_BUTTON, RIGHT_MOUSE_BUTTON  # noqa: E402

LEFT_HELD = (1, 0, 0)
RIGHT_HELD = (0, 0, 1)
NONE_HELD = (0, 0, 0)


class AppTestCase(unittest.TestCase):
    """Creates a fresh App per test and offers event helpers."""

    def setUp(self) -> None:
        pygame.init()
        self.app = App()

    def tearDown(self) -> None:
        pygame.quit()

    def pixel(self, cell: Cell) -> tuple[int, int]:
        rect = self.app.renderer.grid_rect
        half = theme.CELL_SIZE // 2
        return rect.left + cell.col * theme.CELL_SIZE + half, rect.top + cell.row * theme.CELL_SIZE + half

    def press(self, button: int, position: tuple[int, int]) -> None:
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=position))

    def move(self, position: tuple[int, int], buttons: tuple[int, int, int]) -> None:
        self.app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=position, rel=(0, 0), buttons=buttons))

    def release(self, button: int, position: tuple[int, int]) -> None:
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=button, pos=position))

    def key(self, key: int, character: str = "") -> None:
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=character, scancode=0))

    def finish_search(self) -> None:
        while self.app.pathfinder.status in (SearchStatus.RUNNING, SearchStatus.PAUSED):
            self.app.pathfinder.step()


class AppInputTests(AppTestCase):
    def test_window_size_and_title(self) -> None:
        width, height = self.app.renderer.screen.get_size()
        grid_rect = self.app.renderer.grid_rect
        self.assertEqual(pygame.display.get_caption()[0], "Pathfinding")
        self.assertEqual(grid_rect.size, (config.GRID_COLS * theme.CELL_SIZE, config.GRID_ROWS * theme.CELL_SIZE))
        self.assertTrue(pygame.Rect(0, 0, width, height).contains(grid_rect))
        self.assertTrue(pygame.Rect(0, 0, width, height).contains(self.app.renderer.panel_rect))
        self.assertGreater(self.app.renderer.panel_rect.top, grid_rect.bottom)

    def test_every_cell_maps_back_from_its_pixel(self) -> None:
        for row in range(config.GRID_ROWS):
            for col in range(config.GRID_COLS):
                self.assertEqual(self.app.renderer.cell_at(self.pixel(Cell(row, col))), Cell(row, col))

    def test_left_click_adds_and_right_click_removes_wall(self) -> None:
        cell = Cell(2, 2)
        self.press(LEFT_MOUSE_BUTTON, self.pixel(cell))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(cell))
        self.assertTrue(self.app.grid.is_wall(cell))

        self.press(RIGHT_MOUSE_BUTTON, self.pixel(cell))
        self.release(RIGHT_MOUSE_BUTTON, self.pixel(cell))
        self.assertFalse(self.app.grid.is_wall(cell))
        self.assertIs(self.app.drag_mode, DragMode.NONE)

    def test_fast_drag_draws_continuous_wall_and_right_drag_erases(self) -> None:
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.move(self.pixel(Cell(0, 9)), LEFT_HELD)  # Jumps over cells 1..8.
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 9)))
        self.assertTrue(all(self.app.grid.is_wall(Cell(0, c)) for c in range(10)))

        self.press(RIGHT_MOUSE_BUTTON, self.pixel(Cell(0, 2)))
        self.move(self.pixel(Cell(0, 5)), RIGHT_HELD)
        self.release(RIGHT_MOUSE_BUTTON, self.pixel(Cell(0, 5)))
        self.assertEqual(self.app.grid.wall_count, 6)

    def test_drag_moves_start_and_target(self) -> None:
        start, target = self.app.grid.start, self.app.grid.target
        self.press(LEFT_MOUSE_BUTTON, self.pixel(start))
        self.assertIs(self.app.drag_mode, DragMode.MOVE_START)
        self.move(self.pixel(Cell(0, 0)), LEFT_HELD)
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.assertEqual(self.app.grid.start, Cell(0, 0))

        self.press(LEFT_MOUSE_BUTTON, self.pixel(target))
        self.move(self.pixel(Cell(0, 0)), LEFT_HELD)  # Occupied by start: rejected.
        self.assertEqual(self.app.grid.target, target)
        self.move(self.pixel(Cell(19, 49)), LEFT_HELD)
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(19, 49)))
        self.assertEqual(self.app.grid.target, Cell(19, 49))
        self.assertEqual(self.app.grid.wall_count, 0, "moving endpoints must not draw walls")

    def test_drawing_over_endpoints_does_not_wall_them(self) -> None:
        start = self.app.grid.start
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(start.row, 0)))
        self.move(self.pixel(Cell(start.row, config.GRID_COLS - 1)), LEFT_HELD)
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(start.row, config.GRID_COLS - 1)))
        self.assertFalse(self.app.grid.is_wall(self.app.grid.start))
        self.assertFalse(self.app.grid.is_wall(self.app.grid.target))
        self.assertEqual(self.app.grid.wall_count, config.GRID_COLS - 2)

    def test_clicks_outside_grid_are_ignored(self) -> None:
        width, height = self.app.renderer.screen.get_size()
        outside = [(0, 0), (width - 1, height - 1), (5, self.app.renderer.grid_rect.centery),
                   self.app.renderer.grid_rect.bottomright, (-50, -50), (width + 100, height + 100)]
        for position in outside:
            for button in (LEFT_MOUSE_BUTTON, 2, RIGHT_MOUSE_BUTTON, 4, 5):
                self.press(button, position)
                self.move(position, LEFT_HELD)
                self.release(button, position)
        self.assertEqual(self.app.grid.wall_count, 0)
        self.assertIs(self.app.drag_mode, DragMode.NONE)

    def test_drag_leaving_grid_does_not_bridge_exit_and_entry(self) -> None:
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.move((0, 0), LEFT_HELD)  # Leave the grid...
        self.move(self.pixel(Cell(0, 5)), LEFT_HELD)  # ...and re-enter elsewhere.
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 5)))
        self.assertEqual(self.app.grid.wall_count, 2)

    def test_missed_release_and_focus_loss_end_drag(self) -> None:
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(1, 1)))
        self.move(self.pixel(Cell(1, 3)), NONE_HELD)  # Release happened elsewhere.
        self.assertIs(self.app.drag_mode, DragMode.NONE)
        self.assertFalse(self.app.grid.is_wall(Cell(1, 3)))

        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(1, 1)))
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertIs(self.app.drag_mode, DragMode.NONE)

    def test_keyboard_shortcuts(self) -> None:
        self.app.grid.add_wall(Cell(0, 0))
        self.app.grid.move_start(Cell(5, 5))
        self.key(pygame.K_c)
        self.assertEqual(self.app.grid.wall_count, 0)
        self.assertEqual(self.app.grid.start, Cell(5, 5))

        self.app.grid.add_wall(Cell(0, 0))
        self.key(pygame.K_r)
        self.assertEqual(self.app.grid.wall_count, 0)
        self.assertEqual(self.app.grid.start, Cell(*config.DEFAULT_START))

        self.key(pygame.K_ESCAPE)
        self.assertFalse(self.app.running)

    def test_run_loop_processes_queue_and_exits_on_quit(self) -> None:
        cell = Cell(4, 4)
        for event in (
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=LEFT_MOUSE_BUTTON, pos=self.pixel(cell)),
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=LEFT_MOUSE_BUTTON, pos=self.pixel(cell)),
            pygame.event.Event(pygame.QUIT),
        ):
            pygame.event.post(event)
        self.app.run()
        self.assertTrue(self.app.grid.is_wall(cell))
        self.assertFalse(self.app.running)


class AppSearchTests(AppTestCase):
    """Search controls wired through the real event handling and frame loop."""

    def test_space_starts_pauses_and_resumes(self) -> None:
        self.key(pygame.K_SPACE)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)
        self.key(pygame.K_SPACE)
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)
        self.key(pygame.K_SPACE)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)
        self.finish_search()
        self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)

    def test_clear_search_key_preserves_walls(self) -> None:
        for row in range(5):
            self.app.grid.add_wall(Cell(row, 20))
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.key(pygame.K_x)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.assertEqual(self.app.grid.wall_count, 5)
        self.assertEqual(self.app.pathfinder.path_cells, frozenset())

    def test_mouse_edit_invalidates_displayed_path(self) -> None:
        self.key(pygame.K_SPACE)
        self.finish_search()
        path_cell = sorted(self.app.pathfinder.path_cells - {self.app.grid.start, self.app.grid.target})[0]
        self.press(LEFT_MOUSE_BUTTON, self.pixel(path_cell))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(path_cell))
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.assertEqual(self.app.pathfinder.path_cells, frozenset())

    def test_pressing_endpoint_without_moving_keeps_result(self) -> None:
        self.key(pygame.K_SPACE)
        self.finish_search()
        start = self.app.grid.start
        self.press(LEFT_MOUSE_BUTTON, self.pixel(start))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(start))
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)

    def test_speed_keys(self) -> None:
        initial = self.app.pathfinder.steps_per_second
        self.key(pygame.K_UP)
        self.assertGreater(self.app.pathfinder.steps_per_second, initial)
        self.key(pygame.K_DOWN)
        self.key(pygame.K_MINUS, "-")
        self.assertLess(self.app.pathfinder.steps_per_second, initial)
        self.key(pygame.K_EQUALS, "+")
        self.assertEqual(self.app.pathfinder.steps_per_second, initial)

    def test_search_spans_frames_and_input_is_handled_meanwhile(self) -> None:
        """The loop keeps processing events while BFS is still running."""
        self.app.pathfinder.slower()
        self.key(pygame.K_SPACE)
        frame_times = []
        for _ in range(5):
            started = time.perf_counter()
            self.app.run_frame()
            frame_times.append(time.perf_counter() - started)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING, "search must not finish in one go")
        progress = self.app.pathfinder.expanded_count
        self.assertGreater(progress, 0)

        # A pause request queued mid-search is honoured on the very next frame.
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", scancode=0))
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)
        self.assertLess(max(frame_times), 0.25, f"frames took {frame_times}")

    def test_fastest_speed_frames_stay_short(self) -> None:
        for _ in range(len(config.SPEED_LEVELS)):
            self.key(pygame.K_UP)
        self.key(pygame.K_SPACE)
        worst = 0.0
        while self.app.pathfinder.status is SearchStatus.RUNNING:
            started = time.perf_counter()
            self.app.run_frame()
            worst = max(worst, time.perf_counter() - started)
        self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)
        self.assertLess(worst, 0.25)



class AppAlgorithmTests(AppTestCase):
    """Algorithm selection and comparison through real key events."""

    def test_number_keys_select_algorithm_and_reset_stale_state(self) -> None:
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.key(pygame.K_2)
        self.assertIs(self.app.pathfinder.algorithm, Algorithm.ASTAR)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.assertEqual(self.app.pathfinder.path_cells, frozenset())
        self.app.run_frame()  # The header must draw the new selection without errors.

        self.key(pygame.K_SPACE)
        self.finish_search()
        self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)
        self.key(pygame.K_KP1)
        self.assertIs(self.app.pathfinder.algorithm, Algorithm.BFS)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)

    def test_b_toggles_comparison_and_edit_invalidates_it(self) -> None:
        self.key(pygame.K_b)
        report = self.app.pathfinder.comparison
        self.assertIsNotNone(report)
        self.assertEqual(report.repetitions, config.COMPARISON_REPETITIONS)
        bfs_entry, astar_entry = report.entries
        self.assertEqual(bfs_entry.result.path_length, astar_entry.result.path_length)
        self.app.run_frame()  # Draw the overlay.

        self.key(pygame.K_b)
        self.assertIsNone(self.app.pathfinder.comparison)

        self.key(pygame.K_b)
        cell = Cell(0, 0)
        self.press(LEFT_MOUSE_BUTTON, self.pixel(cell))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(cell))
        self.assertIsNone(self.app.pathfinder.comparison)

    def test_comparison_keeps_paused_animation(self) -> None:
        self.key(pygame.K_2)
        self.key(pygame.K_SPACE)
        self.app.pathfinder.step()
        self.key(pygame.K_SPACE)
        expanded = self.app.pathfinder.expanded_count
        self.key(pygame.K_b)
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)
        self.assertEqual(self.app.pathfinder.expanded_count, expanded)
        self.assertIs(self.app.pathfinder.algorithm, Algorithm.ASTAR)

    def test_astar_animation_spans_frames_and_stays_responsive(self) -> None:
        self.key(pygame.K_2)
        self.app.pathfinder.slower()
        self.key(pygame.K_SPACE)
        for _ in range(3):
            self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ", scancode=0))
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)

class AppHybridTests(AppTestCase):
    """Hybrid mode through real key/mouse events and the real frame loop."""

    MAX_FRAMES = 600

    def run_until(self, condition) -> list[float]:
        frame_times = []
        for _ in range(self.MAX_FRAMES):
            if condition():
                return frame_times
            started = time.perf_counter()
            self.app.run_frame()
            frame_times.append(time.perf_counter() - started)
        self.fail("condition not reached within frame limit")

    def test_key_3_selects_hybrid_and_space_starts_session(self) -> None:
        self.key(pygame.K_3)
        self.assertIs(self.app.pathfinder.algorithm, Algorithm.HYBRID)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.key(pygame.K_SPACE)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)
        self.finish_search()
        self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)
        self.app.run_frame()  # Header and hybrid statistics draw without errors.

    def test_mouse_stroke_across_route_triggers_one_replan_without_blocking(self) -> None:
        for _ in range(len(config.SPEED_LEVELS)):
            self.key(pygame.K_UP)
        self.key(pygame.K_3)
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.assertIn(Cell(10, 25), self.app.pathfinder.path_cells)

        # Draw a wall down column 25 (gap left at the bottom row), one cell per frame.
        stroke = [Cell(row, 25) for row in range(config.GRID_ROWS - 1)]
        frame_times = []
        route_row = self.app.grid.start.row
        self.press(LEFT_MOUSE_BUTTON, self.pixel(stroke[0]))
        for cell in stroke[1:]:
            self.move(self.pixel(cell), LEFT_HELD)
            started = time.perf_counter()
            self.app.run_frame()
            frame_times.append(time.perf_counter() - started)
            if cell.row < route_row:
                # Walls added off the route cannot change the optimal result: kept.
                self.assertIs(self.app.pathfinder.status, SearchStatus.FOUND)
                continue
            self.assertIs(self.app.pathfinder.status, SearchStatus.REPLANNING)
            self.assertEqual(self.app.pathfinder.path_cells, frozenset(), "old route hidden at once")
            self.assertEqual(self.app.pathfinder.replan_count, 0, "no replan while the stroke continues")
        self.release(LEFT_MOUSE_BUTTON, self.pixel(stroke[-1]))

        frame_times += self.run_until(lambda: self.app.pathfinder.status is SearchStatus.FOUND)
        self.assertEqual(self.app.pathfinder.replan_count, 1, "the whole stroke coalesced into one replan")
        self.assertTrue(self.app.pathfinder.path_cells.isdisjoint(stroke))
        self.assertIn(Cell(config.GRID_ROWS - 1, 25), self.app.pathfinder.path_cells)
        self.assertLess(max(frame_times), 0.25, "a frame blocked the UI")

    def test_header_explains_pending_replan_while_paused(self) -> None:
        self.key(pygame.K_3)
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.app.grid.remove_wall(Cell(0, 0))  # No-op: not a wall, so no replan.
        self.app.grid.move_target(Cell(0, 0))  # Real edit -> replan pending.
        self.app.pathfinder.update(0.0)
        self.key(pygame.K_SPACE)
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)
        self.assertEqual(status_text(self.app.pathfinder)[0], PAUSED_REPLAN_TEXT)
        self.app.run_frame()

    def test_edits_in_hybrid_mode_before_start_do_nothing(self) -> None:
        self.key(pygame.K_3)
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        for _ in range(30):
            self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)

    def test_x_and_algorithm_keys_end_hybrid_session(self) -> None:
        self.key(pygame.K_3)
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.key(pygame.K_x)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.key(pygame.K_SPACE)
        self.finish_search()
        self.key(pygame.K_1)
        self.assertIs(self.app.pathfinder.algorithm, Algorithm.BFS)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.app.run_frame()
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE, "BFS mode never auto-replans")

class AppToolbarTests(AppTestCase):
    """Clickable toolbar buttons, their states, and the restyled layout."""

    def click(self, button) -> None:
        center = self.app.renderer.button_rect(button).center
        self.press(LEFT_MOUSE_BUTTON, center)
        self.release(LEFT_MOUSE_BUTTON, center)

    def test_mode_buttons_select_algorithm(self) -> None:
        for button, algorithm in MODE_BUTTONS.items():
            self.click(button)
            self.assertIs(self.app.pathfinder.algorithm, algorithm)
            self.assertTrue(is_button_active(button, self.app.pathfinder))
            others = [other for other in MODE_BUTTONS if other is not button]
            self.assertFalse(any(is_button_active(other, self.app.pathfinder) for other in others))

    def test_start_button_cycles_start_pause_resume(self) -> None:
        self.assertEqual(start_button_label(self.app.pathfinder), "Start")
        self.click(Button.START)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)
        self.assertEqual(start_button_label(self.app.pathfinder), "Pause")
        self.click(Button.START)
        self.assertIs(self.app.pathfinder.status, SearchStatus.PAUSED)
        self.assertEqual(start_button_label(self.app.pathfinder), "Resume")
        self.click(Button.START)
        self.assertIs(self.app.pathfinder.status, SearchStatus.RUNNING)

    def test_clear_button_is_disabled_when_idle_and_clears_search(self) -> None:
        self.assertFalse(is_button_enabled(Button.CLEAR, self.app.pathfinder))
        self.click(Button.CLEAR)  # Disabled: no effect, no error.
        self.click(Button.START)
        self.finish_search()
        self.assertTrue(is_button_enabled(Button.CLEAR, self.app.pathfinder))
        self.click(Button.CLEAR)
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)

    def test_compare_button_toggles_overlay(self) -> None:
        self.click(Button.COMPARE)
        self.assertIsNotNone(self.app.pathfinder.comparison)
        self.assertTrue(is_button_active(Button.COMPARE, self.app.pathfinder))
        self.app.run_frame()
        self.click(Button.COMPARE)
        self.assertIsNone(self.app.pathfinder.comparison)

    def test_speed_buttons_change_speed_and_disable_at_limits(self) -> None:
        initial = self.app.pathfinder.steps_per_second
        self.click(Button.FASTER)
        self.assertGreater(self.app.pathfinder.steps_per_second, initial)
        for _ in range(len(config.SPEED_LEVELS)):
            self.click(Button.SLOWER)
        self.assertEqual(self.app.pathfinder.steps_per_second, config.SPEED_LEVELS[0])
        self.assertFalse(is_button_enabled(Button.SLOWER, self.app.pathfinder))
        for _ in range(len(config.SPEED_LEVELS)):
            self.click(Button.FASTER)
        self.assertEqual(self.app.pathfinder.steps_per_second, config.SPEED_LEVELS[-1])
        self.assertFalse(is_button_enabled(Button.FASTER, self.app.pathfinder))

    def test_buttons_do_not_draw_walls_or_start_drags(self) -> None:
        for button in Button:
            self.click(button)
            self.assertIs(self.app.drag_mode, DragMode.NONE)
        right_center = self.app.renderer.button_rect(Button.BFS).center
        self.press(RIGHT_MOUSE_BUTTON, right_center)  # Right click on a button: ignored.
        self.assertIs(self.app.drag_mode, DragMode.NONE)
        self.assertEqual(self.app.grid.wall_count, 0)

    def test_drag_passing_over_toolbar_keeps_drawing_on_grid(self) -> None:
        self.press(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 0)))
        self.move(self.app.renderer.button_rect(Button.CLEAR).center, LEFT_HELD)  # Over a button.
        self.move(self.pixel(Cell(0, 3)), LEFT_HELD)
        self.release(LEFT_MOUSE_BUTTON, self.pixel(Cell(0, 3)))
        self.assertEqual(self.app.grid.wall_count, 2, "only cells under the pointer; no click on the button")
        self.assertIs(self.app.pathfinder.status, SearchStatus.IDLE)

    def test_layout_has_no_overlaps_or_clipping(self) -> None:
        renderer = self.app.renderer
        window = renderer.screen.get_rect()
        rects = {button: renderer.button_rect(button) for button in Button}
        for button, rect in rects.items():
            self.assertTrue(window.contains(rect), button)
            self.assertFalse(rect.colliderect(renderer.grid_rect), button)
            self.assertFalse(rect.colliderect(renderer.panel_rect), button)
            labels = START_LABELS if button is Button.START else (BUTTON_LABELS[button],)
            for label in labels:
                self.assertLess(renderer.fonts.button.size(label)[0], rect.width, label)
        buttons = list(rects.values())
        for index, rect in enumerate(buttons):
            self.assertEqual(rect.collidelist(buttons[index + 1:]), -1, "buttons overlap")
        cards = [renderer.layout.stats_card, renderer.layout.legend_card, renderer.layout.shortcuts_card]
        for index, card in enumerate(cards):
            self.assertTrue(window.contains(card))
            self.assertEqual(card.collidelist(cards[index + 1:]), -1, "cards overlap")

    def test_status_texts_are_friendly_and_fit_the_stats_card(self) -> None:
        renderer = self.app.renderer
        card = renderer.layout.stats_card
        label_width = renderer.fonts.text.size(STATUS_LABEL)[0]
        room = card.width - 2 * theme.CARD_PADDING - label_width - theme.PAIR_GAP
        texts = [text for text, _ in STATUS_TEXT.values()] + list(HYBRID_PHASE_TEXT.values()) + [HYBRID_FOUND_TEXT]
        for text in texts:
            self.assertLessEqual(renderer.fonts.text.size(text)[0], room, text)
        raw_names = {member.name for enum in (SearchStatus, HybridPhase) for member in enum}
        for text in texts:
            self.assertFalse(raw_names & set(text.replace("·", " ").split()), text)

    def test_header_has_no_status_text(self) -> None:
        """The header only shows the logo, title and subtitle; status lives in the stats card."""
        layout = self.app.renderer.layout
        self.assertGreaterEqual(layout.title_right, layout.title_left + self.app.renderer.fonts.subtitle.size(SUBTITLE)[0])
        self.key(pygame.K_SPACE)
        self.app.run_frame()
        first_row = content.stat_rows(self.app.grid, self.app.pathfinder)[0]
        self.assertEqual(first_row[:2], (STATUS_LABEL, "Searching"))

    def test_hover_states_render_and_show_hand_cursor(self) -> None:
        for button in Button:
            center = self.app.renderer.button_rect(button).center
            self.app.renderer.draw(self.app.grid, self.app.pathfinder, None, center)
            self.assertIs(self.app.renderer.button_at(center), button)
        self.app._update_cursor(None, self.app.renderer.button_rect(Button.START).center)
        self.assertTrue(self.app._hand_cursor)
        self.app._update_cursor(None, self.app.renderer.button_rect(Button.CLEAR).center)  # Disabled.
        self.assertFalse(self.app._hand_cursor)

if __name__ == "__main__":
    unittest.main()
