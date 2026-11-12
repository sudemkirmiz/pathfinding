"""Lightweight animation helpers driven by a millisecond clock.

Pure Python (no Pygame). Nothing here sleeps or blocks: every helper simply
answers "what should be shown at time ``now_ms``?" when the frame is drawn.
"""

from collections.abc import Hashable, Iterable

from ui.theme import Color


def ease_out_cubic(t: float) -> float:
    """Fast start, gentle finish; ``t`` in 0..1."""
    return 1 - (1 - t) ** 3


def lerp_color(start: Color, end: Color, t: float) -> Color:
    return tuple(round(a + (b - a) * t) for a, b in zip(start, end))


class ColorFader:
    """Fades each key's displayed color toward its latest target color.

    Changes to or from any of ``instant_colors`` are applied immediately (for
    walls and endpoints, which must react to the mouse without delay).
    """

    def __init__(self, duration_ms: int, instant_colors: Iterable[Color] = ()) -> None:
        self._duration_ms = duration_ms
        self._instant = frozenset(instant_colors)
        self._targets: dict[Hashable, Color] = {}
        self._transitions: dict[Hashable, tuple[Color, int]] = {}  # key -> (from color, start time)

    def color(self, key: Hashable, target: Color, now_ms: int, delay_ms: int = 0) -> Color:
        """Displayed color of ``key`` at ``now_ms`` given its current ``target``."""
        previous = self._targets.get(key)
        if previous != target:
            self._targets[key] = target
            if previous is None or previous in self._instant or target in self._instant:
                self._transitions.pop(key, None)
            else:
                self._transitions[key] = (self._displayed(key, previous, now_ms), now_ms + delay_ms)
        return self._displayed(key, target, now_ms)

    def is_animating(self) -> bool:
        return bool(self._transitions)

    def _displayed(self, key: Hashable, target: Color, now_ms: int) -> Color:
        transition = self._transitions.get(key)
        if transition is None:
            return target
        start_color, start_ms = transition
        elapsed = now_ms - start_ms
        if elapsed >= self._duration_ms:
            del self._transitions[key]
            return target
        if elapsed <= 0:
            return start_color
        return lerp_color(start_color, target, ease_out_cubic(elapsed / self._duration_ms))


class HoverFader:
    """Per-key hover amount (0..1) that eases in when hovered and out when left."""

    def __init__(self, duration_ms: int) -> None:
        self._duration_ms = duration_ms
        self._amounts: dict[Hashable, float] = {}
        self._last_ms: int | None = None

    def update(self, hovered: Hashable | None, now_ms: int) -> None:
        step = 1.0 if self._last_ms is None else (now_ms - self._last_ms) / self._duration_ms
        self._last_ms = now_ms
        keys = set(self._amounts) | ({hovered} if hovered is not None else set())
        for key in keys:
            goal = 1.0 if key == hovered else 0.0
            amount = self._amounts.get(key, 0.0)
            amount = min(goal, amount + step) if goal > amount else max(goal, amount - step)
            if amount > 0:
                self._amounts[key] = amount
            else:
                self._amounts.pop(key, None)

    def amount(self, key: Hashable) -> float:
        return ease_out_cubic(self._amounts.get(key, 0.0))
