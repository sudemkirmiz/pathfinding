"""Pathfinding visualizer entry point: application lifecycle and input handling."""

from enum import Enum, auto

import pygame

import config
from algorithms.registry import Algorithm
from core.grid import Cell, Grid, line_cells
from core.pathfinder import Pathfinder
from ui.controls import MODE_BUTTONS, Button, is_button_enabled
from ui.display import center_window, choose_scale, enable_dpi_awareness, usable_area
from ui.renderer import Renderer

LEFT_MOUSE_BUTTON = 1
RIGHT_MOUSE_BUTTON = 3
# Index of each button inside the ``MOUSEMOTION`` event's ``buttons`` tuple.
MOTION_BUTTON_INDEX = {LEFT_MOUSE_BUTTON: 0, RIGHT_MOUSE_BUTTON: 2}
MILLISECONDS_PER_SECOND = 1000
# Speed keys: arrows work on every keyboard layout; +/- also via typed character.
FASTER_KEYS = {pygame.K_UP, pygame.K_KP_PLUS}
SLOWER_KEYS = {pygame.K_DOWN, pygame.K_KP_MINUS}
FASTER_CHARACTERS = {"+"}
SLOWER_CHARACTERS = {"-"}
ALGORITHM_KEYS = {
    pygame.K_1: Algorithm.BFS,
    pygame.K_KP1: Algorithm.BFS,
    pygame.K_2: Algorithm.ASTAR,
    pygame.K_KP2: Algorithm.ASTAR,
    pygame.K_3: Algorithm.HYBRID,
    pygame.K_KP3: Algorithm.HYBRID,
}


class DragMode(Enum):
    """What the current mouse drag does to the cells it passes over."""

    NONE = auto()
    DRAW_WALLS = auto()
    ERASE_WALLS = auto()
    MOVE_START = auto()
    MOVE_TARGET = auto()


class App:
    """Owns the grid, pathfinder and renderer and translates user input into actions.

    Grid edits never touch the pathfinder directly: every edit bumps
    ``Grid.revision`` and on its next update the pathfinder discards (BFS / A*)
    or replans (hybrid) any search made for an older revision, so a stale
    result can never be drawn.
    """

    def __init__(self) -> None:
        self.grid = Grid(
            config.GRID_ROWS,
            config.GRID_COLS,
            start=Cell(*config.DEFAULT_START),
            target=Cell(*config.DEFAULT_TARGET),
        )
        self.pathfinder = Pathfinder(
            self.grid,
            config.SPEED_LEVELS,
            config.DEFAULT_SPEED_INDEX,
            replan_settle_seconds=config.REPLAN_SETTLE_SECONDS,
        )
        self.renderer = Renderer(config.GRID_ROWS, config.GRID_COLS)
        self.clock = pygame.time.Clock()
        self._frame_seconds = 0.0
        self.running = True
        self.drag_mode = DragMode.NONE
        self._drag_button: int | None = None
        self._last_drag_cell: Cell | None = None
        self._hand_cursor = False

    def run(self) -> None:
        while self.running:
            self.run_frame()

    def run_frame(self) -> None:
        """Process input, advance the search by this frame's share of steps, draw.

        The search never runs to completion inside a frame, so input stays
        responsive however long the search is.
        """
        for event in pygame.event.get():
            self.handle_event(event)
        self.pathfinder.update(self._frame_seconds)
        mouse_position = pygame.mouse.get_pos() if pygame.mouse.get_focused() else None
        hovered = self.renderer.cell_at(mouse_position) if mouse_position is not None else None
        self._update_cursor(hovered, mouse_position)
        self.renderer.draw(self.grid, self.pathfinder, hovered, mouse_position)
        self._frame_seconds = self.clock.tick(config.FPS) / MILLISECONDS_PER_SECOND

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key, event.unicode)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event.button, event.pos)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event.pos, event.buttons)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == self._drag_button:
                self._end_drag()
        elif event.type == pygame.WINDOWFOCUSLOST:
            # The button release may happen in another window and never reach us.
            self._end_drag()

    def _handle_key(self, key: int, character: str) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_SPACE:
            self.pathfinder.toggle()
        elif key == pygame.K_x:
            self.pathfinder.clear()
        elif key in ALGORITHM_KEYS:
            self.pathfinder.select(ALGORITHM_KEYS[key])
        elif key == pygame.K_b:
            self._toggle_comparison()
        elif key in FASTER_KEYS or character in FASTER_CHARACTERS:
            self.pathfinder.faster()
        elif key in SLOWER_KEYS or character in SLOWER_CHARACTERS:
            self.pathfinder.slower()
        elif key == pygame.K_c:
            self._end_drag()
            self.grid.clear_walls()
        elif key == pygame.K_r:
            self._end_drag()
            self.grid.reset()

    def _toggle_comparison(self) -> None:
        """Show a BFS / A* comparison for the current grid, or hide the visible one.

        The comparison runs synchronously (a few tens of milliseconds on a
        20x50 grid) and does not touch the animated search.
        """
        if self.pathfinder.comparison is not None:
            self.pathfinder.hide_comparison()
        else:
            self.pathfinder.compare(config.COMPARISON_REPETITIONS, config.COMPARISON_WARMUP_RUNS)

    def _press_button(self, button: Button) -> None:
        """Run a toolbar button's action; each mirrors a keyboard shortcut."""
        if not is_button_enabled(button, self.pathfinder):
            return
        if button in MODE_BUTTONS:
            self.pathfinder.select(MODE_BUTTONS[button])
        elif button is Button.START:
            self.pathfinder.toggle()
        elif button is Button.CLEAR:
            self.pathfinder.clear()
        elif button is Button.COMPARE:
            self._toggle_comparison()
        elif button is Button.SLOWER:
            self.pathfinder.slower()
        elif button is Button.FASTER:
            self.pathfinder.faster()

    def _handle_mouse_down(self, button: int, position: tuple[int, int]) -> None:
        if self.drag_mode is not DragMode.NONE:
            return  # Ignore a second button while a drag is in progress.
        toolbar_button = self.renderer.button_at(position)
        if toolbar_button is not None:
            if button == LEFT_MOUSE_BUTTON:
                self._press_button(toolbar_button)
            return  # Clicks on the toolbar never start a grid drag.
        cell = self.renderer.cell_at(position)
        if cell is None:
            return

        if button == LEFT_MOUSE_BUTTON:
            if cell == self.grid.start:
                self.drag_mode = DragMode.MOVE_START
            elif cell == self.grid.target:
                self.drag_mode = DragMode.MOVE_TARGET
            else:
                self.drag_mode = DragMode.DRAW_WALLS
        elif button == RIGHT_MOUSE_BUTTON:
            self.drag_mode = DragMode.ERASE_WALLS
        else:
            return  # Middle button and scroll wheel are not used.

        self._drag_button = button
        self._apply_drag(cell)

    def _handle_mouse_motion(self, position: tuple[int, int], buttons: tuple[int, int, int]) -> None:
        if self._drag_button is None:
            return
        if not buttons[MOTION_BUTTON_INDEX[self._drag_button]]:
            self._end_drag()  # Button was released without us seeing the event.
            return
        self._apply_drag(self.renderer.cell_at(position))

    def _apply_drag(self, cell: Cell | None) -> None:
        if cell is None:
            # Pointer left the grid: don't connect the exit and re-entry points.
            self._last_drag_cell = None
            return

        if self.drag_mode is DragMode.MOVE_START:
            self.grid.move_start(cell)
        elif self.drag_mode is DragMode.MOVE_TARGET:
            self.grid.move_target(cell)
        elif self.drag_mode in (DragMode.DRAW_WALLS, DragMode.ERASE_WALLS):
            edit = self.grid.add_wall if self.drag_mode is DragMode.DRAW_WALLS else self.grid.remove_wall
            stroke = line_cells(self._last_drag_cell, cell) if self._last_drag_cell is not None else [cell]
            for stroke_cell in stroke:
                edit(stroke_cell)
        self._last_drag_cell = cell

    def _end_drag(self) -> None:
        self.drag_mode = DragMode.NONE
        self._drag_button = None
        self._last_drag_cell = None

    def _update_cursor(self, hovered: Cell | None, mouse_position: tuple[int, int] | None) -> None:
        """Show a hand cursor over endpoints and enabled buttons, or while moving an endpoint."""
        toolbar_button = self.renderer.button_at(mouse_position) if mouse_position is not None else None
        want_hand = self.drag_mode in (DragMode.MOVE_START, DragMode.MOVE_TARGET) or (
            self.drag_mode is DragMode.NONE
            and (
                hovered in (self.grid.start, self.grid.target)
                or (toolbar_button is not None and is_button_enabled(toolbar_button, self.pathfinder))
            )
        )
        if want_hand != self._hand_cursor:
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if want_hand else pygame.SYSTEM_CURSOR_ARROW)
            except pygame.error:
                pass  # Some video drivers (e.g. headless ones) have no system cursors; it is cosmetic.
            self._hand_cursor = want_hand


def main() -> None:
    enable_dpi_awareness()
    pygame.init()
    try:
        area = usable_area()
        _, window_size = choose_scale(config.GRID_ROWS, config.GRID_COLS, area.size)
        center_window(area, window_size)
        App().run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
