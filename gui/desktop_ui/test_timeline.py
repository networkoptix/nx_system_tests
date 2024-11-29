# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import unittest

from gui.desktop_ui.media_capturing import RGBColor
from gui.desktop_ui.timeline import _make_stripe


class TestTimeline(unittest.TestCase):

    def test_stripe(self):
        red = RGBColor(255, 0, 0)
        green = RGBColor(0, 255, 0)
        grey = RGBColor(128, 128, 128)
        row = [grey, grey, green, green, green, red, green, grey, green, red, grey, grey, red]
        stripe = _make_stripe(row)
        cleaned_stripe = stripe.dissolve(grey)
        [red_thin, red_with_gap] = cleaned_stripe.get_chunks(red)
        [green_start, green_with_thin_gap] = cleaned_stripe.get_chunks(green)
        self.assertEqual(green_start.start, 0)
        self.assertEqual(green_start.end, 4)
        self.assertEqual(red_thin.start, 5)
        self.assertEqual(red_thin.end, 5)
        self.assertEqual(green_with_thin_gap.start, 6)
        self.assertEqual(green_with_thin_gap.end, 8)
        self.assertEqual(red_with_gap.start, 9)
        self.assertEqual(red_with_gap.end, 12)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
