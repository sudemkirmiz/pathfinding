"""Frame rendering: header, toolbar, animated grid, info cards and comparison overlay.

The renderer only *displays* state and reports which button lies under a
point. It reads the grid model and the pathfinder but never changes them and
makes no algorithmic decisions. Animations are purely visual and never delay
the search itself.
"""

from math import ceil

import pygame

import config
from core.benchmark import ComparisonReport
from core.grid import Cell, Grid
from core.pathfinder import Pathfinder
from ui import content, theme
from ui.animation import ColorFader, HoverFader, ease_out_cubic
from ui.controls import (
    BUTTON_LABELS,
    MODE_BUTTONS,
    Button,
    Tone,
    is_button_active,
    is_button_enabled,
    start_button_label,
)
from ui.layout import Layout, build_layout, shortcut_column_width
from ui.theme import Color
from ui.widgets import (
    ButtonStyle,
    draw_button,
    draw_card,
    draw_group,
    draw_keycap,
    draw_logo,
    keycap_width,
    load_fonts,
)

TONE_COLORS: dict[Tone, Color] = {
    Tone.NEUTRAL: theme.NEUTRAL_STATUS_COLOR,
    Tone.ACTIVE: theme.ACTIVE_STATUS_COLOR,
    Tone.WARNING: theme.WARNING_COLOR,
    Tone.SUCCESS: theme.SUCCESS_COLOR,
    Tone.ERROR: theme.ERROR_COLOR,
}
BUTTON_STYLES: dict[Button, ButtonStyle] = {
    **{button: ButtonStyle.SEGMENT for button in MODE_BUTTONS},
    Button.START: ButtonStyle.PRIMARY,
    Button.CLEAR: ButtonStyle.SECONDARY,
    Button.COMPARE: ButtonStyle.SECONDARY,
    Button.SLOWER: ButtonStyle.SEGMENT,
    Button.FASTER: ButtonStyle.SEGMENT,
}


class Renderer:
    """Owns the Pygame window and draws the whole frame."""

    def __init__(self, rows: int, cols: int) -> None:
        self.fonts = load_fonts()
        self.layout: Layout = build_layout(rows, cols, self.fonts)
        self.grid_rect = self.layout.grid
        self.panel_rect = self.layout.panel
        self._start_label = self.fonts.cell_label.render("S", True, theme.CELL_LABEL_COLOR)
        self._target_label = self.fonts.cell_label.render("T", True, theme.CELL_LABEL_COLOR)

        self._cell_fader = ColorFader(
            theme.CELL_FADE_MS, instant_colors=(theme.WALL_COLOR, theme.START_COLOR, theme.TARGET_COLOR)
        )
        self._hover = HoverFader(theme.HOVER_FADE_MS)
        self._path_order: dict[Cell, int] = {}
        self._path_source: tuple[Cell, ...] = ()
        self._overlay_report: ComparisonReport | None = None
        self._overlay_since_ms = 0

        self.screen = pygame.display.set_mode(self.layout.size)
        pygame.display.set_caption(config.WINDOW_TITLE)

    # --- Geometry -------------------------------------------------------------

    def cell_at(self, position: tuple[int, int]) -> Cell | None:
        """Map a window pixel to a grid cell, or None if it is outside the grid."""
        if not self.grid_rect.collidepoint(position):
            return None
        x, y = position
        return Cell((y - self.grid_rect.top) // theme.CELL_SIZE, (x - self.grid_rect.left) // theme.CELL_SIZE)

    def button_at(self, position: tuple[int, int]) -> Button | None:
        """The toolbar button under a window pixel, if any."""
        for button, rect in self.layout.buttons.items():
            if rect.collidepoint(position):
                return button
        return None

    def button_rect(self, button: Button) -> pygame.Rect:
        return self.layout.buttons[button].copy()

    def _cell_rect(self, cell: Cell) -> pygame.Rect:
        rect = pygame.Rect(
            self.grid_rect.left + cell.col * theme.CELL_SIZE,
            self.grid_rect.top + cell.row * theme.CELL_SIZE,
            theme.CELL_SIZE,
            theme.CELL_SIZE,
        )
        return rect.inflate(-theme.CELL_GAP, -theme.CELL_GAP)

    # --- Frame ------------------------------------------------------------------

    def draw(
        self,
        grid: Grid,
        pathfinder: Pathfinder,
        hovered: Cell | None,
        mouse_position: tuple[int, int] | None = None,
        now_ms: int | None = None,
    ) -> None:
        """Render one complete frame at time ``now_ms`` (default: the Pygame clock)."""
        now_ms = pygame.time.get_ticks() if now_ms is None else now_ms
        hovered_button = self.button_at(mouse_position) if mouse_position is not None else None
        if hovered_button is not None and not is_button_enabled(hovered_button, pathfinder):
            hovered_button = None
        self._hover.update(hovered_button, now_ms)

        self.screen.fill(theme.BACKGROUND_COLOR)
        self._draw_header()
        self._draw_toolbar(pathfinder)
        self._draw_grid(grid, pathfinder, hovered, now_ms)
        self._draw_stats(grid, pathfinder)
        self._draw_legend()
        self._draw_shortcuts()
        self._draw_comparison(pathfinder.comparison, now_ms)
        pygame.display.flip()

    # --- Header and toolbar --------------------------------------------------------

    def _draw_header(self) -> None:
        center_y = theme.HEADER_HEIGHT // 2
        draw_logo(self.screen, (theme.PAGE_MARGIN, center_y - theme.LOGO_SIZE // 2))

        title = self.fonts.title.render(config.WINDOW_TITLE, True, theme.TITLE_COLOR)
        subtitle = self.fonts.subtitle.render(content.SUBTITLE, True, theme.MUTED_TEXT_COLOR)
        top = center_y - (title.get_height() + subtitle.get_height()) // 2
        self.screen.blit(title, (self.layout.title_left, top))
        self.screen.blit(subtitle, (self.layout.title_left, top + title.get_height()))

    def _draw_toolbar(self, pathfinder: Pathfinder) -> None:
        draw_group(self.screen, self.layout.mode_group)
        draw_group(self.screen, self.layout.speed_group)
        for button, rect in self.layout.buttons.items():
            draw_button(
                self.screen,
                rect,
                start_button_label(pathfinder) if button is Button.START else BUTTON_LABELS[button],
                self.fonts.button,
                style=BUTTON_STYLES[button],
                enabled=is_button_enabled(button, pathfinder),
                active=is_button_active(button, pathfinder),
                hover=self._hover.amount(button),
            )
        speed = self.fonts.text.render(content.format_speed(pathfinder.steps_per_second), True, theme.TEXT_COLOR)
        center = (
            (self.layout.buttons[Button.SLOWER].right + self.layout.buttons[Button.FASTER].left) // 2,
            self.layout.speed_group.centery,
        )
        self.screen.blit(speed, speed.get_rect(center=center))

    # --- Grid ---------------------------------------------------------------------

    def _draw_grid(self, grid: Grid, pathfinder: Pathfinder, hovered: Cell | None, now_ms: int) -> None:
        draw_card(self.screen, self.layout.grid_card, color=theme.GRID_BACKGROUND_COLOR)
        path_delays = self._path_reveal_delays(pathfinder)
        for row in range(grid.rows):
            for col in range(grid.cols):
                cell = Cell(row, col)
                target = self._cell_color(grid, pathfinder, cell)
                color = self._cell_fader.color(cell, target, now_ms, path_delays.get(cell, 0))
                pygame.draw.rect(self.screen, color, self._cell_rect(cell), border_radius=theme.CELL_RADIUS)

        for cell, label in ((grid.start, self._start_label), (grid.target, self._target_label)):
            self.screen.blit(label, label.get_rect(center=self._cell_rect(cell).center))

        if hovered is not None:
            pygame.draw.rect(
                self.screen, theme.HOVER_COLOR, self._cell_rect(hovered),
                width=theme.HOVER_BORDER_WIDTH, border_radius=theme.CELL_RADIUS,
            )

    def _path_reveal_delays(self, pathfinder: Pathfinder) -> dict[Cell, int]:
        """Stagger the path's fade-in from start to target so the route visibly grows."""
        path = pathfinder.result.path if pathfinder.result is not None and pathfinder.path_cells else ()
        if path != self._path_source:
            self._path_source = path
            step = min(theme.PATH_REVEAL_STEP_MAX_MS, theme.PATH_REVEAL_TOTAL_MS // max(len(path), 1))
            self._path_order = {cell: index * step for index, cell in enumerate(path)}
        return self._path_order

    @staticmethod
    def _cell_color(grid: Grid, pathfinder: Pathfinder, cell: Cell) -> Color:
        """Target color of a cell; endpoints and walls take precedence over search state."""
        if cell == grid.start:
            return theme.START_COLOR
        if cell == grid.target:
            return theme.TARGET_COLOR
        if grid.is_wall(cell):
            return theme.WALL_COLOR
        if cell in pathfinder.path_cells:
            return theme.PATH_COLOR
        if cell == pathfinder.current:
            return theme.CURRENT_COLOR
        if cell in pathfinder.frontier:
            return theme.FRONTIER_COLOR
        if cell in pathfinder.expanded:
            return theme.EXPANDED_COLOR
        return theme.EMPTY_CELL_COLOR

    # --- Info cards -------------------------------------------------------------------

    def _draw_card_heading(self, card: pygame.Rect, text: str) -> int:
        """Draw a card and its heading; return the y coordinate of the first row."""
        draw_card(self.screen, card)
        top = card.top + theme.CARD_PADDING
        heading = self.fonts.heading.render(text, True, theme.HEADING_COLOR)
        self.screen.blit(heading, (card.left + theme.CARD_PADDING, top))
        return top + self.fonts.heading.get_linesize() + theme.CARD_HEADING_GAP

    @staticmethod
    def _row_center_y(first_row_y: int, index: int) -> int:
        return first_row_y + index * theme.LINE_SPACING + theme.LINE_SPACING // 2

    def _draw_stats(self, grid: Grid, pathfinder: Pathfinder) -> None:
        card = self.layout.stats_card
        first_row_y = self._draw_card_heading(card, "STATISTICS")
        left, right = card.left + theme.CARD_PADDING, card.right - theme.CARD_PADDING
        for index, (label, value, tone) in enumerate(content.stat_rows(grid, pathfinder)):
            center_y = self._row_center_y(first_row_y, index)
            value_color = theme.TEXT_COLOR if tone is None else TONE_COLORS[tone]
            label_surface = self.fonts.text.render(label, True, theme.MUTED_TEXT_COLOR)
            value_surface = self.fonts.text.render(value, True, value_color)
            self.screen.blit(label_surface, label_surface.get_rect(midleft=(left, center_y)))
            self.screen.blit(value_surface, value_surface.get_rect(midright=(right, center_y)))

    def _draw_legend(self) -> None:
        card = self.layout.legend_card
        first_row_y = self._draw_card_heading(card, "LEGEND")
        rows_per_column = ceil(len(content.LEGEND) / theme.LEGEND_COLUMNS)
        for index, (label, color) in enumerate(content.LEGEND):
            column, row = divmod(index, rows_per_column)
            item_x = card.left + theme.CARD_PADDING + column * (self.layout.legend_item_width + theme.CARD_COLUMN_GAP)
            center_y = self._row_center_y(first_row_y, row)
            swatch = pygame.Rect(0, 0, theme.SWATCH_SIZE, theme.SWATCH_SIZE)
            swatch.midleft = (item_x, center_y)
            pygame.draw.rect(self.screen, color, swatch, border_radius=theme.CELL_RADIUS)
            pygame.draw.rect(
                self.screen, theme.STRONG_BORDER_COLOR, swatch, width=theme.BORDER_WIDTH, border_radius=theme.CELL_RADIUS
            )
            text = self.fonts.text.render(label, True, theme.TEXT_COLOR)
            self.screen.blit(text, text.get_rect(midleft=(swatch.right + theme.SWATCH_TEXT_GAP, center_y)))

    def _draw_shortcuts(self) -> None:
        card = self.layout.shortcuts_card
        first_row_y = self._draw_card_heading(card, "SHORTCUTS")
        x = card.left + theme.CARD_PADDING
        for column in content.SHORTCUT_COLUMNS:
            key_width = max(keycap_width(self.fonts.small, key) for key, _ in column)
            for index, (key, text) in enumerate(column):
                center_y = self._row_center_y(first_row_y, index)
                draw_keycap(self.screen, (x, center_y), key, self.fonts.small)
                text_surface = self.fonts.text.render(text, True, theme.MUTED_TEXT_COLOR)
                self.screen.blit(text_surface, text_surface.get_rect(midleft=(x + key_width + theme.PAIR_GAP, center_y)))
            x += shortcut_column_width(self.fonts, column) + theme.CARD_COLUMN_GAP

    # --- Comparison overlay -------------------------------------------------------------

    def _draw_comparison(self, report: ComparisonReport | None, now_ms: int) -> None:
        """Fade in the BFS / A* comparison as a card centered over the grid."""
        if report is not self._overlay_report:
            self._overlay_report = report
            self._overlay_since_ms = now_ms
        if report is None:
            return
        progress = ease_out_cubic(min(1.0, (now_ms - self._overlay_since_ms) / theme.OVERLAY_FADE_MS))

        dim = pygame.Surface(self.layout.grid_card.size, pygame.SRCALPHA)
        pygame.draw.rect(
            dim, (*theme.BACKGROUND_COLOR, round(theme.OVERLAY_DIM_ALPHA * progress)), dim.get_rect(),
            border_radius=theme.CARD_RADIUS,
        )
        self.screen.blit(dim, self.layout.grid_card.topleft)

        card_surface = self._comparison_card(report)
        card_surface.set_alpha(round(255 * progress))
        self.screen.blit(card_surface, card_surface.get_rect(center=self.grid_rect.center))

    def _comparison_card(self, report: ComparisonReport) -> pygame.Surface:
        # Table columns of (text, color); column 0 holds the row labels.
        columns: list[list[tuple[str, Color]]] = [
            [("", theme.MUTED_TEXT_COLOR)] + [(label, theme.MUTED_TEXT_COLOR) for label in content.COMPARISON_ROW_LABELS]
        ]
        for entry in report.entries:
            result = entry.result
            columns.append([
                (entry.algorithm.value, theme.TITLE_COLOR),
                ("Found", theme.SUCCESS_COLOR) if result.found else ("No path", theme.ERROR_COLOR),
                (content.format_path(result.path_length) if result.found else content.NO_VALUE, theme.TEXT_COLOR),
                (str(result.expanded_count), theme.TEXT_COLOR),
                (str(result.discovered_count), theme.TEXT_COLOR),
                (content.format_milliseconds(entry.median_seconds), theme.TEXT_COLOR),
            ])

        title = self.fonts.heading.render(content.COMPARISON_TITLE, True, theme.HEADING_COLOR)
        notes = [
            self.fonts.small.render(content.comparison_note(report), True, theme.MUTED_TEXT_COLOR),
            self.fonts.small.render(content.COMPARISON_CLOSE_HINT, True, theme.MUTED_TEXT_COLOR),
        ]
        column_widths = [max(self.fonts.text.size(text)[0] for text, _ in column) for column in columns]
        table_width = sum(column_widths) + theme.OVERLAY_COLUMN_GAP * (len(columns) - 1)
        content_width = max([table_width, title.get_width()] + [note.get_width() for note in notes])
        row_count = len(columns[0])
        title_height = self.fonts.heading.get_linesize() + theme.CARD_HEADING_GAP
        note_height = self.fonts.small.get_linesize()
        size = (
            content_width + 2 * theme.OVERLAY_PADDING,
            2 * theme.OVERLAY_PADDING + title_height + row_count * theme.OVERLAY_ROW_SPACING
            + theme.OVERLAY_NOTE_GAP + len(notes) * note_height,
        )

        surface = pygame.Surface(size, pygame.SRCALPHA)
        draw_card(surface, surface.get_rect(), radius=theme.OVERLAY_RADIUS)
        left = y = theme.OVERLAY_PADDING
        surface.blit(title, (left, y))
        y += title_height
        x = left
        for column, width in zip(columns, column_widths):
            for row, (text, color) in enumerate(column):
                rendered = self.fonts.text.render(text, True, color)
                surface.blit(rendered, rendered.get_rect(midleft=(x, y + row * theme.OVERLAY_ROW_SPACING + theme.OVERLAY_ROW_SPACING // 2)))
            x += width + theme.OVERLAY_COLUMN_GAP
        y += row_count * theme.OVERLAY_ROW_SPACING + theme.OVERLAY_NOTE_GAP
        for note in notes:
            surface.blit(note, (left, y))
            y += note_height
        return surface
