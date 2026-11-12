"""UI scaling: every scale keeps the layout consistent and the largest fitting scale is chosen."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import config  # noqa: E402
from core.grid import Cell  # noqa: E402
from main import App  # noqa: E402
from ui import theme  # noqa: E402
from ui.display import MIN_SCALE, SCALE_STEP, choose_scale  # noqa: E402
from ui.layout import build_layout  # noqa: E402
from ui.widgets import load_fonts  # noqa: E402

ROWS, COLS = config.GRID_ROWS, config.GRID_COLS


class ScaleTests(unittest.TestCase):
    def setUp(self) -> None:
        pygame.init()

    def tearDown(self) -> None:
        theme.apply_scale(1.0)
        pygame.quit()

    def test_apply_scale_multiplies_sizes_and_restores(self) -> None:
        theme.apply_scale(2.0)
        self.assertEqual((theme.CELL_SIZE, theme.TEXT_FONT_SIZE, theme.BORDER_WIDTH), (42, 28, 2))
        theme.apply_scale(1.0)
        self.assertEqual((theme.CELL_SIZE, theme.TEXT_FONT_SIZE, theme.BORDER_WIDTH), (21, 14, 1))
        with self.assertRaises(ValueError):
            theme.apply_scale(0)

    def test_chosen_scale_is_the_largest_that_fits(self) -> None:
        for available in ((1427, 980), (1904, 1000), (2560, 1380), (1300, 690)):
            with self.subTest(available=available):
                scale, size = choose_scale(ROWS, COLS, available)
                self.assertLessEqual(size[0], available[0])
                self.assertLessEqual(size[1], available[1])
                theme.apply_scale(round(scale + SCALE_STEP, 2))
                bigger = build_layout(ROWS, COLS, load_fonts()).size
                self.assertTrue(bigger[0] > available[0] or bigger[1] > available[1], "a larger step would also fit")

    def test_tiny_screen_falls_back_to_minimum_scale(self) -> None:
        scale, _ = choose_scale(ROWS, COLS, (400, 300))
        self.assertEqual(scale, MIN_SCALE)

    def test_app_is_consistent_at_large_scale(self) -> None:
        theme.apply_scale(1.5)
        app = App()
        renderer = app.renderer
        window = renderer.screen.get_rect()
        self.assertEqual(renderer.grid_rect.size, (COLS * theme.CELL_SIZE, ROWS * theme.CELL_SIZE))
        for cell in (Cell(0, 0), Cell(ROWS - 1, COLS - 1), Cell(7, 31)):
            x = renderer.grid_rect.left + cell.col * theme.CELL_SIZE + theme.CELL_SIZE // 2
            y = renderer.grid_rect.top + cell.row * theme.CELL_SIZE + theme.CELL_SIZE // 2
            self.assertEqual(renderer.cell_at((x, y)), cell)
        rects = list(renderer.layout.buttons.values())
        for index, rect in enumerate(rects):
            self.assertTrue(window.contains(rect))
            self.assertEqual(rect.collidelist(rects[index + 1:]), -1)
        app.run_frame()


if __name__ == "__main__":
    unittest.main()
