# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math


class CIELABColor:

    def __init__(self, l_star: float, a_star: float, b_star: float):
        if not 0.0 <= l_star <= 100.0:
            raise ValueError(
                "Luminance value must be between 0.0 and 100.0 borders included. "
                f"Got: {l_star}")
        elif not -128.0 <= a_star <= 127:
            raise ValueError(
                "Red-Green axis value should be between -128.0 and 127.0 borders included. "
                f"Got: {a_star}")
        elif not -128.0 <= b_star <= 127:
            raise ValueError(
                "Blue-Yellow axis value should be between -128.0 and 127.0 borders included. "
                f"Got: {b_star}")
        self._luminance = l_star
        self._red_green = a_star
        self._blue_yellow = b_star

    def _calculate_delta(self, other: 'CIELABColor') -> float:
        # See: https://www.ulprospector.com/knowledge/10780/pc-the-cielab-lab-system-the-method-to-quantify-colors-of-coatings/
        euclidean_distance = math.dist(
            (self._luminance, self._red_green, self._blue_yellow),
            (other._luminance, other._red_green, other._blue_yellow),
            )
        _logger.debug("%r: CIELAB Distance with %r is %.06f", self, other, euclidean_distance)
        return euclidean_distance

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        delta = self._calculate_delta(other)
        # See: https://www.viewsonic.com/library/creative-work/what-is-delta-e-and-why-is-it-important-for-color-accuracy/
        return delta <= 2.0

    def is_shade_of(self, other: 'CIELABColor') -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        delta = self._calculate_delta(other)
        # See: https://www.viewsonic.com/library/creative-work/what-is-delta-e-and-why-is-it-important-for-color-accuracy/
        return delta <= 10.0

    def is_close_to(self, other: 'CIELABColor') -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        delta = self._calculate_delta(other)
        # See: https://www.viewsonic.com/library/creative-work/what-is-delta-e-and-why-is-it-important-for-color-accuracy/
        return delta <= 49.0

    def __repr__(self):
        name = self.__class__.__name__
        return f'{name}({self._luminance:.03f}, {self._red_green:.03f}, {self._blue_yellow:.03f})'


class RGBColor(CIELABColor):

    def __init__(self, red: int, green: int, blue: int):
        if not 0 <= red <= 255:
            raise ValueError(f"Red color value must be in range 0-255. Received: {red}")
        if not 0 <= green <= 255:
            raise ValueError(f"Green color value must be in range 0-255. Received: {green}")
        if not 0 <= blue <= 255:
            raise ValueError(f"Blue color value must be in range 0-255. Received: {blue}")
        x, y, z = _rgb_to_xyz(red, green, blue)
        luminance, red_green, blue_yellow = _xyz_to_cielab(x, y, z)
        super().__init__(luminance, red_green, blue_yellow)
        self._red = red
        self._green = green
        self._blue = blue

    def __repr__(self):
        return f'{self.__class__.__name__}({self._red:03d}, {self._green:03d}, {self._blue:03d})'


def _rgb_to_xyz(red: int, green: int, blue: int) -> tuple[float, float, float]:
    # See: http://www.easyrgb.com/en/math.php
    # See: https://colorcalculations.wordpress.com/xyz-to-rgb/
    red = _xyz_transform_single_rgb_color(red)
    green = _xyz_transform_single_rgb_color(green)
    blue = _xyz_transform_single_rgb_color(blue)
    x = red * 0.4124 + green * 0.3576 + blue * 0.1805
    y = red * 0.2126 + green * 0.7152 + blue * 0.0722
    z = red * 0.0193 + green * 0.1192 + blue * 0.9505
    return x, y, z


def _xyz_transform_single_rgb_color(color: int) -> float:
    result = color / 255
    result = (((result + 0.055) / 1.055) ** 2.4) if (result > 0.04045) else (result / 12.92)
    result *= 100
    return result


def _xyz_to_cielab(x: float, y: float, z: float) -> tuple[float, float, float]:
    # See: http://www.easyrgb.com/en/math.php
    # See: https://rip94550.wordpress.com/2011/07/04/color-cielab-and-tristimulus-xyz/
    x, y, z = _d65_2_deg_transform(x, y, z)
    x_transformed = _transform_xyz_axis(x)
    y_transformed = _transform_xyz_axis(y)
    z_transformed = _transform_xyz_axis(z)
    luminance = (116 * y_transformed) - 16
    red_green = 500 * (x_transformed - y_transformed)
    blue_yellow = 200 * (y_transformed - z_transformed)
    return luminance, red_green, blue_yellow


def _d65_2_deg_transform(x: float, y: float, z: float) -> tuple[float, float, float]:
    # Daylight, sRGB, Adobe-RGB 2 degrees angle
    x_ref = x / 95.047
    y_ref = y / 100.0
    z_ref = z / 108.883
    return x_ref, y_ref, z_ref


def _transform_xyz_axis(axis: float) -> float:
    return axis ** (1 / 3) if axis > 0.008856 else (7.787 * axis) + (16 / 116)


_logger = logging.getLogger(__name__)
