"""Fonts and reusable drawing primitives: cards, buttons, keycaps and the logo."""

from dataclasses import dataclass
from enum import Enum, auto

import pygame

from ui import theme
from ui.animation import lerp_color
from ui.theme import Color


@dataclass(frozen=True)
class Fonts:
    title: pygame.font.Font
    subtitle: pygame.font.Font
    text: pygame.font.Font
    button: pygame.font.Font
    small: pygame.font.Font
    heading: pygame.font.Font
    cell_label: pygame.font.Font


def load_fonts() -> Fonts:
    def font(size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont(theme.FONT_NAME, size, bold=bold)

    return Fonts(
        title=font(theme.TITLE_FONT_SIZE, bold=True),
        subtitle=font(theme.SUBTITLE_FONT_SIZE),
        text=font(theme.TEXT_FONT_SIZE),
        button=font(theme.BUTTON_FONT_SIZE, bold=True),
        small=font(theme.SMALL_FONT_SIZE),
        heading=font(theme.HEADING_FONT_SIZE, bold=True),
        cell_label=font(theme.CELL_LABEL_FONT_SIZE, bold=True),
    )


class ButtonStyle(Enum):
    PRIMARY = auto()    # Filled accent: the main action.
    SECONDARY = auto()  # Outlined; tinted with the accent while toggled on.
    SEGMENT = auto()    # Part of a segmented group; filled while selected.


def draw_card(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: Color = theme.SURFACE_COLOR,
    radius: int | None = None,
) -> None:
    radius = theme.CARD_RADIUS if radius is None else radius
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, theme.BORDER_COLOR, rect, width=theme.BORDER_WIDTH, border_radius=radius)


def draw_button(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    font: pygame.font.Font,
    *,
    style: ButtonStyle,
    enabled: bool,
    active: bool,
    hover: float,
) -> None:
    """Draw one button; ``hover`` (0..1) blends in the hover look smoothly."""
    border: Color | None
    if not enabled:
        background = theme.RAISED_COLOR if style is not ButtonStyle.SEGMENT else None
        border, text_color = None, theme.DISABLED_TEXT_COLOR
    elif style is ButtonStyle.PRIMARY:
        background = lerp_color(theme.ACCENT_COLOR, theme.ACCENT_HOVER_COLOR, hover)
        border, text_color = None, theme.ON_ACCENT_COLOR
    elif style is ButtonStyle.SEGMENT:
        if active:
            background, text_color = theme.ACCENT_COLOR, theme.ON_ACCENT_COLOR
        else:
            background = lerp_color(theme.RAISED_COLOR, theme.HOVER_SURFACE_COLOR, hover) if hover else None
            text_color = lerp_color(theme.MUTED_TEXT_COLOR, theme.TEXT_COLOR, hover)
        border = None
    elif active:
        background = lerp_color(theme.RAISED_COLOR, theme.ACCENT_COLOR, 0.22 + 0.08 * hover)
        border, text_color = theme.ACCENT_COLOR, theme.ACCENT_TEXT_COLOR
    else:
        background = lerp_color(theme.RAISED_COLOR, theme.HOVER_SURFACE_COLOR, hover)
        border = lerp_color(theme.STRONG_BORDER_COLOR, theme.ACCENT_COLOR, 0.6 * hover)
        text_color = theme.TEXT_COLOR

    if background is not None:
        pygame.draw.rect(surface, background, rect, border_radius=theme.BUTTON_RADIUS)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=theme.BORDER_WIDTH, border_radius=theme.BUTTON_RADIUS)
    text = font.render(label, True, text_color)
    surface.blit(text, text.get_rect(center=rect.center))


def draw_group(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Background of a segmented or speed control group."""
    radius = theme.BUTTON_RADIUS + theme.GROUP_INSET
    pygame.draw.rect(surface, theme.RAISED_COLOR, rect, border_radius=radius)
    pygame.draw.rect(surface, theme.STRONG_BORDER_COLOR, rect, width=theme.BORDER_WIDTH, border_radius=radius)


def keycap_width(font: pygame.font.Font, key: str) -> int:
    return font.size(key)[0] + 2 * theme.KEYCAP_PADDING_X


def draw_keycap(surface: pygame.Surface, midleft: tuple[int, int], key: str, font: pygame.font.Font) -> None:
    rect = pygame.Rect(0, 0, keycap_width(font, key), theme.KEYCAP_HEIGHT)
    rect.midleft = midleft
    pygame.draw.rect(surface, theme.RAISED_COLOR, rect, border_radius=theme.KEYCAP_RADIUS)
    pygame.draw.rect(surface, theme.STRONG_BORDER_COLOR, rect, width=theme.BORDER_WIDTH, border_radius=theme.KEYCAP_RADIUS)
    text = font.render(key, True, theme.TEXT_COLOR)
    surface.blit(text, text.get_rect(center=rect.center))


def draw_logo(surface: pygame.Surface, topleft: tuple[int, int]) -> None:
    """Rounded accent square with a small route glyph (three connected waypoints)."""
    size = theme.LOGO_SIZE
    rect = pygame.Rect(topleft, (size, size))
    pygame.draw.rect(surface, theme.ACCENT_COLOR, rect, border_radius=theme.LOGO_RADIUS)
    # Waypoints as fractions of the logo size: bottom-left, top-middle, right.
    points = [(rect.left + round(size * fx), rect.top + round(size * fy)) for fx, fy in ((0.25, 0.70), (0.50, 0.32), (0.76, 0.58))]
    pygame.draw.lines(surface, theme.ON_ACCENT_COLOR, False, points, theme.LOGO_LINE_WIDTH)
    for point in points:
        pygame.draw.circle(surface, theme.ON_ACCENT_COLOR, point, theme.LOGO_DOT_RADIUS)
