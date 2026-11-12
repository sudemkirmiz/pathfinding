"""Window layout: every rectangle the renderer draws into, computed once at startup.

Sizes are measured from the actual text, so labels cannot overflow; if
something does not fit, ``build_layout`` raises instead of drawing a broken UI.
"""

from dataclasses import dataclass
from math import ceil

import pygame

import config
from ui import content, theme
from ui.controls import BUTTON_LABELS, MODE_BUTTONS, START_LABELS, Button
from ui.widgets import Fonts, keycap_width


@dataclass(frozen=True)
class Layout:
    size: tuple[int, int]
    title_left: int
    title_right: int                 # Right edge of the title / subtitle block.
    buttons: dict[Button, pygame.Rect]
    mode_group: pygame.Rect          # Background of the BFS / A* / Hybrid segments.
    speed_group: pygame.Rect         # Background of the − / speed / + control.
    grid_card: pygame.Rect
    grid: pygame.Rect                # Exact area of the cells (mouse mapping).
    panel: pygame.Rect               # Area of the three info cards.
    stats_card: pygame.Rect
    legend_card: pygame.Rect
    shortcuts_card: pygame.Rect
    legend_item_width: int


def build_layout(rows: int, cols: int, fonts: Fonts) -> Layout:
    width = 2 * (theme.PAGE_MARGIN + theme.GRID_CARD_PADDING) + cols * theme.CELL_SIZE
    content_width = width - 2 * theme.PAGE_MARGIN

    title_left = theme.PAGE_MARGIN + theme.LOGO_SIZE + theme.LOGO_TEXT_GAP
    title_right = title_left + max(
        fonts.title.size(config.WINDOW_TITLE)[0], fonts.subtitle.size(content.SUBTITLE)[0]
    )

    toolbar_top = theme.HEADER_HEIGHT
    buttons, mode_group, speed_group = _layout_toolbar(toolbar_top, width, fonts)

    grid_card = pygame.Rect(
        theme.PAGE_MARGIN,
        toolbar_top + theme.TOOLBAR_HEIGHT + theme.SECTION_GAP,
        content_width,
        rows * theme.CELL_SIZE + 2 * theme.GRID_CARD_PADDING,
    )
    grid = grid_card.inflate(-2 * theme.GRID_CARD_PADDING, -2 * theme.GRID_CARD_PADDING)

    legend_item_width = theme.SWATCH_SIZE + theme.SWATCH_TEXT_GAP + max(
        fonts.text.size(label)[0] for label, _ in content.LEGEND
    )
    panel = pygame.Rect(theme.PAGE_MARGIN, grid_card.bottom + theme.SECTION_GAP, content_width, _card_height(fonts))
    stats_card, legend_card, shortcuts_card = _layout_cards(panel, rows, cols, fonts, legend_item_width)

    return Layout(
        size=(width, panel.bottom + theme.PAGE_MARGIN),
        title_left=title_left,
        title_right=title_right,
        buttons=buttons,
        mode_group=mode_group,
        speed_group=speed_group,
        grid_card=grid_card,
        grid=grid,
        panel=panel,
        stats_card=stats_card,
        legend_card=legend_card,
        shortcuts_card=shortcuts_card,
        legend_item_width=legend_item_width,
    )


def shortcut_column_width(fonts: Fonts, column: tuple[tuple[str, str], ...]) -> int:
    key_width = max(keycap_width(fonts.small, key) for key, _ in column)
    return key_width + theme.PAIR_GAP + max(fonts.text.size(text)[0] for _, text in column)


def _button_width(fonts: Fonts, *labels: str) -> int:
    return max(fonts.button.size(label)[0] for label in labels) + 2 * theme.BUTTON_PADDING_X


def _layout_toolbar(
    top: int, window_width: int, fonts: Fonts
) -> tuple[dict[Button, pygame.Rect], pygame.Rect, pygame.Rect]:
    """Mode selector and actions on the left, speed control on the right."""
    inset = theme.GROUP_INSET
    inner_height = theme.TOOLBAR_HEIGHT - 2 * inset
    buttons: dict[Button, pygame.Rect] = {}

    segment_width = _button_width(fonts, *(BUTTON_LABELS[button] for button in MODE_BUTTONS))
    mode_group = pygame.Rect(
        theme.PAGE_MARGIN, top, len(MODE_BUTTONS) * segment_width + 2 * inset, theme.TOOLBAR_HEIGHT
    )
    for index, button in enumerate(MODE_BUTTONS):
        buttons[button] = pygame.Rect(mode_group.left + inset + index * segment_width, top + inset, segment_width, inner_height)

    x = mode_group.right + theme.GROUP_GAP
    for button, width in (
        (Button.START, _button_width(fonts, *START_LABELS)),
        (Button.CLEAR, _button_width(fonts, BUTTON_LABELS[Button.CLEAR])),
        (Button.COMPARE, _button_width(fonts, BUTTON_LABELS[Button.COMPARE])),
    ):
        buttons[button] = pygame.Rect(x, top, width, theme.TOOLBAR_HEIGHT)
        x += width + theme.BUTTON_GAP

    label_width = max(fonts.text.size(content.format_speed(speed))[0] for speed in config.SPEED_LEVELS)
    group_width = 2 * inner_height + label_width + 2 * theme.SPEED_LABEL_PADDING + 2 * inset
    speed_group = pygame.Rect(window_width - theme.PAGE_MARGIN - group_width, top, group_width, theme.TOOLBAR_HEIGHT)
    buttons[Button.SLOWER] = pygame.Rect(speed_group.left + inset, top + inset, inner_height, inner_height)
    buttons[Button.FASTER] = pygame.Rect(speed_group.right - inset - inner_height, top + inset, inner_height, inner_height)

    if buttons[Button.COMPARE].right + theme.GROUP_GAP > speed_group.left:
        raise ValueError("Toolbar buttons do not fit the window width.")
    return buttons, mode_group, speed_group


def _card_height(fonts: Fonts) -> int:
    rows = max(
        len(content.STAT_LABELS),
        len(content.HYBRID_STAT_LABELS),
        ceil(len(content.LEGEND) / theme.LEGEND_COLUMNS),
        *(len(column) for column in content.SHORTCUT_COLUMNS),
    )
    return 2 * theme.CARD_PADDING + fonts.heading.get_linesize() + theme.CARD_HEADING_GAP + rows * theme.LINE_SPACING


def _layout_cards(
    panel: pygame.Rect, rows: int, cols: int, fonts: Fonts, legend_item_width: int
) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
    """Size the statistics, legend and shortcut cards from their widest content.

    Leftover width is shared equally between the cards.
    """
    widest_label = max(fonts.text.size(label)[0] for label in (*content.STAT_LABELS, *content.HYBRID_STAT_LABELS))
    widest_value = max(fonts.text.size(value)[0] for value in content.widest_stat_values(rows, cols))
    natural = [
        widest_label + theme.PAIR_GAP + widest_value,
        theme.LEGEND_COLUMNS * legend_item_width + (theme.LEGEND_COLUMNS - 1) * theme.CARD_COLUMN_GAP,
        sum(shortcut_column_width(fonts, column) for column in content.SHORTCUT_COLUMNS)
        + (len(content.SHORTCUT_COLUMNS) - 1) * theme.CARD_COLUMN_GAP,
    ]
    natural = [width + 2 * theme.CARD_PADDING for width in natural]
    spare = panel.width - sum(natural) - (len(natural) - 1) * theme.CARD_GAP
    if spare < 0:
        raise ValueError("Info cards do not fit the window width.")

    cards = []
    x = panel.left
    for index, width in enumerate(natural):
        width += spare // len(natural) + (spare % len(natural) if index == len(natural) - 1 else 0)
        cards.append(pygame.Rect(x, panel.top, width, panel.height))
        x += width + theme.CARD_GAP
    return cards[0], cards[1], cards[2]
