# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import unittest

from browser.color import CIELABColor
from browser.color import RGBColor


class TestColor(unittest.TestCase):

    def test_color_eq_neq(self):
        grey = RGBColor(128, 128, 128)
        grey_other = RGBColor(128, 128, 128)
        red = RGBColor(255, 0, 0)
        self.assertEqual(grey, grey_other)
        self.assertNotEqual(red, grey)
        # See: https://convertingcolors.com/rgb-color-0_0_0.html?
        rgb_black = RGBColor(0, 0, 0)
        lab_black = CIELABColor(0.00, 0.00, 0.00)
        self.assertEqual(rgb_black, lab_black)
        # See: https://convertingcolors.com/rgb-color-255_255_255.html
        rgb_white = RGBColor(255, 255, 255)
        lab_white = CIELABColor(100.00, 0.01, -0.01)
        self.assertEqual(rgb_white, lab_white)
        # See: https://convertingcolors.com/rgb-color-255_0_255.html
        rgb_magenta = RGBColor(255, 0, 255)
        lab_magenta = CIELABColor(60.32, 98.25, -60.84)
        self.assertEqual(rgb_magenta, lab_magenta)

    def test_color_is_shade(self):
        grey = RGBColor(128, 128, 128)
        bleached_grey = RGBColor(125, 124, 126)
        self.assertTrue(bleached_grey.is_shade_of(grey))

    def test_color_is_close(self):
        grey = RGBColor(128, 128, 128)
        red = RGBColor(255, 0, 0)
        yellow = RGBColor(255, 255, 0)
        blue = RGBColor(0, 0, 255)
        self.assertFalse(red.is_close_to(yellow))
        self.assertFalse(red.is_close_to(blue))
        self.assertFalse(red.is_close_to(grey))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
