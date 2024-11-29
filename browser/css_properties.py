# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# See: https://www.w3schools.com/cssref/index.php
import re
from pathlib import Path

from browser.color import RGBColor
from browser.webdriver import WebDriverElement


def get_text_color(element: 'WebDriverElement') -> RGBColor:
    return _parse_webdriver_rgba(element.http_get("/css/color"))


def get_background_color(element: 'WebDriverElement') -> RGBColor:
    return _parse_webdriver_rgba(element.get_css_value('background-color'))


def get_visible_color(element: 'WebDriverElement') -> RGBColor:
    # An HTML element may have semi-transparent background color. In this case, the recursive
    # algorithm should be applied blending semi-transparent colors until the root or
    # a non-transparent element is reached.
    script = Path(__file__).with_name('get_visible_color.js').read_text()
    [red, green, blue] = element.execute_javascript_function(script)
    return RGBColor(red, green, blue)


def _parse_webdriver_rgba(value: str) -> RGBColor:
    if not value.startswith("rgba"):
        raise RuntimeError(f"Received unknown color value {value}")
    value = value[4:].lstrip("(").rstrip(")")
    raw_red, raw_green, raw_blue, raw_alpha = value.split(",")
    alpha = float(raw_alpha)
    if alpha != 1.0:
        raise NotImplementedError(
            f"Correct alpha channel handling is not implemented. Alpha value is {alpha}")
    return RGBColor(int(raw_red), int(raw_green), int(raw_blue))


def get_width(element: 'WebDriverElement') -> float:
    value = element.http_get("/css/width")
    if not value.endswith('px'):
        raise RuntimeError(f"Unknown pixel width value received: {value}")
    return float(value[:-2])


# See: https://www.w3schools.com/cssref/pr_border-color.php
def get_borders_style(element: 'WebDriverElement') -> 'BordersStyle':
    value = element.get_css_value("border-color")
    match = _rgb_color_match.findall(value)
    if match is None:
        raise ValueError(f"Can't parse {value} as border style")
    borders_colors_count = len(match)
    if borders_colors_count == 1:
        top = _rgb_from_raw(*match[0])
        bottom = _rgb_from_raw(*match[0])
        left = _rgb_from_raw(*match[0])
        right = _rgb_from_raw(*match[0])
    elif borders_colors_count == 2:
        top = _rgb_from_raw(*match[0])
        bottom = _rgb_from_raw(*match[0])
        left = _rgb_from_raw(*match[1])
        right = _rgb_from_raw(*match[1])
    elif borders_colors_count == 3:
        top = _rgb_from_raw(*match[0])
        bottom = _rgb_from_raw(*match[2])
        left = _rgb_from_raw(*match[1])
        right = _rgb_from_raw(*match[1])
    elif borders_colors_count == 4:
        top = _rgb_from_raw(*match[0])
        bottom = _rgb_from_raw(*match[3])
        left = _rgb_from_raw(*match[1])
        right = _rgb_from_raw(*match[2])
    else:
        raise ValueError(f"Can't parse {value} as border style")
    return BordersStyle(top, bottom, left, right)


_rgb_color_match = re.compile(r'rgb\((?P<red>\d+),\s*(?P<green>\d+),\s*(?P<blue>\d+)\)')


def _rgb_from_raw(red: str, green: str, blue: str) -> RGBColor:
    return RGBColor(int(red), int(green), int(blue))


class BordersStyle:

    def __init__(self, top: RGBColor, bottom: RGBColor, left: RGBColor, right: RGBColor):
        self._top = top
        self._bottom = bottom
        self._left = left
        self._right = right

    def is_encircled_by(self, color: RGBColor) -> bool:
        if self._top.is_close_to(color):
            if self._bottom.is_close_to(color):
                if self._left.is_close_to(color):
                    if self._right.is_close_to(color):
                        return True
        return False

    def __repr__(self):
        return f'<t:{self._top},b:{self._bottom},l:{self._left},r:{self._right}>'
