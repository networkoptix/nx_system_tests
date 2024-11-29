# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import cmath
import math
from typing import Collection
from typing import NamedTuple


class ScreenRectangle(NamedTuple):
    x: int
    y: int
    width: int
    height: int

    def ratio(self):
        return self.width / self.height

    def contains_point(self, point: 'ScreenPoint'):
        return all((
            self.x <= point.x <= self.x + self.width,
            self.y <= point.y <= self.y + self.height,
            ))

    def contains_rectangle(self, other: 'ScreenRectangle'):
        return all((
            self.contains_point(other.top_left()),
            self.contains_point(other.bottom_right()),
            ))

    def displacement_from(self, other: 'ScreenRectangle'):
        return max(
            self.top_left().chessboard_distance(other.top_left()),
            abs(self.width - other.width),
            abs(self.height - other.height),
            )

    def center(self):
        x = self.x + self.width // 2
        y = self.y + self.height // 2
        return ScreenPoint(x, y)

    def top_left(self):
        return ScreenPoint(self.x, self.y)

    def top_center(self):
        return ScreenPoint(self.x + self.width // 2, self.y)

    def top_right(self):
        return ScreenPoint(self.x + self.width, self.y)

    def bottom_left(self):
        return ScreenPoint(self.x, self.y + self.height)

    def bottom_center(self):
        return ScreenPoint(self.x + self.width // 2, self.y + self.height)

    def bottom_right(self):
        return ScreenPoint(self.x + self.width, self.y + self.height)

    def middle_left(self):
        return ScreenPoint(self.x, self.y + self.height // 2)

    def middle_right(self):
        return ScreenPoint(self.x + self.width, self.y + self.height // 2)

    def side_centers(self):
        return [
            self.top_center(),
            self.middle_right(),
            self.bottom_center(),
            self.middle_left(),
            ]

    def axis_scaling(self, x_axis_ratio, y_axis_ratio, max_width, max_height) -> 'ScreenRectangle':
        new_width = _clip(int(self.width * x_axis_ratio), 0, max_width)
        new_x = _clip(int(self.x * x_axis_ratio), 0, max_width - new_width)
        new_height = _clip(int(self.height * y_axis_ratio), 0, max_height)
        new_y = _clip(int(self.y * y_axis_ratio), 0, max_height - new_height)
        return ScreenRectangle(new_x, new_y, new_width, new_height)

    def add_borders(self, border_factor, max_sizes) -> 'ScreenRectangle':
        border = int(self.height * border_factor * 0.5)
        max_sizes = ScreenPoint(*max_sizes)
        new_top_left = self.top_left().up(border).left(border).clip(max_sizes)
        new_bottom_right = self.bottom_right().down(border).right(border).clip(max_sizes)
        new_sizes = new_bottom_right.diff(new_top_left)
        return ScreenRectangle(
            int(new_top_left.x),
            int(new_top_left.y),
            int(new_sizes[0]),
            int(new_sizes[1]),
            )


class ScreenPoint(NamedTuple):
    x: int
    y: int

    def left(self, dx: int):
        return ScreenPoint(self.x - dx, self.y)

    def right(self, dx: int):
        return ScreenPoint(self.x + dx, self.y)

    def up(self, dy: int):
        return ScreenPoint(self.x, self.y - dy)

    def down(self, dy: int):
        return ScreenPoint(self.x, self.y + dy)

    def clip(self, max_limit):
        return ScreenPoint(
            _clip(self.x, 0, max_limit.x),
            _clip(self.y, 0, max_limit.y),
            )

    def diff(self, other: 'ScreenPoint'):
        return self.x - other.x, self.y - other.y

    def _euclidean_distance(self, other: 'ScreenPoint'):
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def euclidean_closest(self, others: Collection['ScreenPoint']):
        return min(others, key=lambda p: self._euclidean_distance(p))

    def chessboard_distance(self, other: 'ScreenPoint'):
        return max(
            abs(self.x - other.x),
            abs(self.y - other.y),
            )

    def transform(self, *, around: 'ScreenPoint', rotate: float, scale: float = 1):
        s = complex(real=self.x, imag=self.y)
        a = complex(real=around.x, imag=around.y)
        r = cmath.rect(scale, math.radians(rotate))
        z = a + r * (s - a)
        return ScreenPoint(int(z.real), int(z.imag))


def _clip(value, min_limit, max_limit):
    return max(min(max_limit, value), min_limit)
