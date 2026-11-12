"""Tests for the time-driven animation helpers (ui.animation); no display needed."""

import unittest

from ui.animation import ColorFader, HoverFader, ease_out_cubic, lerp_color

BLACK, WHITE, RED = (0, 0, 0), (255, 255, 255), (255, 0, 0)
DURATION = 100


class EasingTests(unittest.TestCase):
    def test_ease_and_lerp_endpoints(self) -> None:
        self.assertEqual((ease_out_cubic(0.0), ease_out_cubic(1.0)), (0.0, 1.0))
        self.assertGreater(ease_out_cubic(0.5), 0.5, "ease-out moves fast first")
        self.assertEqual(lerp_color(BLACK, WHITE, 0.0), BLACK)
        self.assertEqual(lerp_color(BLACK, WHITE, 1.0), WHITE)
        self.assertEqual(lerp_color(BLACK, WHITE, 0.5), (128, 128, 128))


class ColorFaderTests(unittest.TestCase):
    def test_first_color_is_shown_immediately(self) -> None:
        fader = ColorFader(DURATION)
        self.assertEqual(fader.color("a", BLACK, now_ms=0), BLACK)
        self.assertFalse(fader.is_animating())

    def test_change_fades_over_duration(self) -> None:
        fader = ColorFader(DURATION)
        fader.color("a", BLACK, 0)
        self.assertEqual(fader.color("a", WHITE, 1000), BLACK, "transition starts from the old color")
        middle = fader.color("a", WHITE, 1050)
        self.assertTrue(BLACK < middle < WHITE)
        self.assertEqual(fader.color("a", WHITE, 1100), WHITE)
        self.assertFalse(fader.is_animating())

    def test_delay_holds_old_color(self) -> None:
        fader = ColorFader(DURATION)
        fader.color("a", BLACK, 0)
        fader.color("a", WHITE, 0, delay_ms=50)
        self.assertEqual(fader.color("a", WHITE, 40), BLACK)
        self.assertEqual(fader.color("a", WHITE, 150), WHITE)

    def test_retarget_mid_fade_continues_from_displayed_color(self) -> None:
        fader = ColorFader(DURATION)
        fader.color("a", BLACK, 0)
        fader.color("a", WHITE, 0)
        shown = fader.color("a", WHITE, 50)
        self.assertEqual(fader.color("a", RED, 50), shown, "no jump when the target changes again")

    def test_instant_colors_skip_the_fade(self) -> None:
        fader = ColorFader(DURATION, instant_colors=(RED,))
        fader.color("a", BLACK, 0)
        self.assertEqual(fader.color("a", RED, 10), RED)
        self.assertEqual(fader.color("a", BLACK, 20), BLACK, "leaving an instant color is instant too")

    def test_keys_are_independent(self) -> None:
        fader = ColorFader(DURATION)
        fader.color("a", BLACK, 0)
        fader.color("b", BLACK, 0)
        fader.color("a", WHITE, 0)
        self.assertEqual(fader.color("b", BLACK, 50), BLACK)


class HoverFaderTests(unittest.TestCase):
    def test_hover_eases_in_and_out(self) -> None:
        fader = HoverFader(DURATION)
        fader.update(None, 0)
        fader.update("button", 50)
        self.assertTrue(0 < fader.amount("button") < 1)
        fader.update("button", 200)
        self.assertEqual(fader.amount("button"), 1.0)
        fader.update(None, 250)
        self.assertTrue(0 < fader.amount("button") < 1)
        fader.update(None, 400)
        self.assertEqual(fader.amount("button"), 0.0)

    def test_moving_between_keys(self) -> None:
        fader = HoverFader(DURATION)
        fader.update("a", 0)
        fader.update("a", 200)
        fader.update("b", 300)
        self.assertEqual((fader.amount("a"), fader.amount("b")), (0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
