"""Display setup: crisp rendering on high-DPI screens and the largest UI scale that fits.

On Windows, a Pygame window is DPI-unaware by default: with display scaling
above 100 % the operating system stretches each finished frame, which makes
text and edges blurry. Declaring the process DPI-aware lets the app draw at the
screen's real resolution, and ``choose_scale`` then enlarges the whole UI
(fonts included) to the biggest size that still fits the usable screen area.
"""

import ctypes
import os
import sys

import pygame

from ui import theme
from ui.layout import build_layout
from ui.widgets import load_fonts

MIN_SCALE = 0.75
MAX_SCALE = 3.0
SCALE_STEP = 0.05
# Without a work-area API (non-Windows), keep this share of the desktop height
# free for menu bars, docks and the window title bar.
FALLBACK_HEIGHT_RESERVE = 0.12

# Win32 constants.
SPI_GETWORKAREA = 0x0030
SM_CXFRAME, SM_CYFRAME, SM_CYCAPTION, SM_CXPADDEDBORDER = 32, 33, 4, 92
PROCESS_SYSTEM_DPI_AWARE = 1


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def enable_dpi_awareness() -> None:
    """Ask Windows not to bitmap-stretch the window; call before creating it."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Older Windows versions.
        except (AttributeError, OSError):
            pass


def usable_area() -> pygame.Rect:
    """Screen area the window's drawing surface may occupy (taskbar and window frame excluded)."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            work = _Rect()
            if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0):
                padding = user32.GetSystemMetrics(SM_CXPADDEDBORDER)
                frame_x = user32.GetSystemMetrics(SM_CXFRAME) + padding
                frame_y = user32.GetSystemMetrics(SM_CYFRAME) + padding
                title = user32.GetSystemMetrics(SM_CYCAPTION) + frame_y
                return pygame.Rect(
                    work.left + frame_x,
                    work.top + title,
                    work.right - work.left - 2 * frame_x,
                    work.bottom - work.top - title - frame_y,
                )
        except (AttributeError, OSError):
            pass
    width, height = pygame.display.get_desktop_sizes()[0]
    reserve = round(height * FALLBACK_HEIGHT_RESERVE)
    return pygame.Rect(0, reserve // 2, width, height - reserve)


def choose_scale(rows: int, cols: int, available: tuple[int, int]) -> tuple[float, tuple[int, int]]:
    """Apply and return the largest scale whose window fits ``available``, with that window size.

    The layout does not grow exactly linearly (font sizes round to whole
    pixels), so a linear estimate is refined by measuring: step up while the
    next scale still fits, otherwise step down until one fits.
    """
    def measure(scale: float) -> tuple[int, int] | None:
        theme.apply_scale(scale)
        size = build_layout(rows, cols, load_fonts()).size
        return size if size[0] <= available[0] and size[1] <= available[1] else None

    theme.apply_scale(1.0)
    base_width, base_height = build_layout(rows, cols, load_fonts()).size
    estimate = min(available[0] / base_width, available[1] / base_height, MAX_SCALE)
    candidate = round(max(MIN_SCALE, int(estimate / SCALE_STEP) * SCALE_STEP), 2)

    size = measure(candidate)
    while size is None and candidate > MIN_SCALE:
        candidate = round(max(MIN_SCALE, candidate - SCALE_STEP), 2)
        size = measure(candidate)
    if size is None:  # Even the minimum scale is too big: use it anyway.
        return candidate, build_layout(rows, cols, load_fonts()).size
    while candidate + SCALE_STEP <= MAX_SCALE:
        bigger = measure(round(candidate + SCALE_STEP, 2))
        if bigger is None:
            break
        candidate, size = round(candidate + SCALE_STEP, 2), bigger
    theme.apply_scale(candidate)
    return candidate, size


def center_window(area: pygame.Rect, size: tuple[int, int]) -> None:
    """Make the next window open centered inside ``area``; call before ``set_mode``."""
    x = area.left + max(0, (area.width - size[0]) // 2)
    y = area.top + max(0, (area.height - size[1]) // 2)
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"
