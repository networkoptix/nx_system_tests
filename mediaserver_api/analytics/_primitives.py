# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from math import isclose

_logger = logging.getLogger(__name__)


class _Interval:

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def contains(self, number):
        return self.start <= number <= self.end

    def expanded(self, accuracy):
        return _Interval(self.start - accuracy, self.end + accuracy)

    def overlaps(self, other, accuracy):
        expanded = other.expanded(accuracy)
        return expanded.contains(self.start) or self.contains(expanded.start)

    @property
    def size(self):
        return self.end - self.start

    def calc_rel_coordinate(self, abs_coordinate: float):
        return self.size - abs(self.size - abs_coordinate % (2 * self.size))


class Rectangle:

    def __init__(self, x1, y1, x2, y2):
        self.x = _Interval(x1, x2)
        self.y = _Interval(y1, y2)
        _logger.debug("Create %r", self)
        self.coordinates_dict = {
            'x1': self.x.start,
            'y1': self.y.start,
            'x2': self.x.end,
            'y2': self.y.end,
            }

    def __repr__(self):
        return (
            f'Rectangle(x1={self.x.start}, y1={self.y.start}, x2={self.x.end}, y2={self.y.end})')

    @classmethod
    def from_box_data(cls, x, y, width, height):
        return cls(x1=x, x2=x + width, y1=y, y2=y + height)

    def overlaps(self, other, x_accuracy, y_accuracy):
        return self.x.overlaps(other.x, x_accuracy) and self.y.overlaps(other.y, y_accuracy)


class NormalizedRectangle(Rectangle):

    def __init__(self, x, y, width, height):
        super().__init__(x, y, x + width, y + height)
        if not self._is_valid():
            raise ValueError(f"{self} has invalid coordinates")

    def _is_valid(self):
        values_ok = all(
            0 <= value <= 1 for value in (self.x.start, self.x.end, self.y.start, self.y.end))
        dimensions_ok = all((self.x.end >= self.x.start, self.y.end >= self.y.start))
        return values_ok and dimensions_ok

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(x={self.x.start}, y={self.y.start}, "
            f"width={self.x.size}, height={self.y.size})"
            )

    def is_close_to(self, other, rel_tolerance=0.001):
        return all([
            isclose(self.x.start, other.x.start, rel_tol=rel_tolerance),
            isclose(self.y.start, other.y.start, rel_tol=rel_tolerance),
            isclose(self.x.end, other.x.end, rel_tol=rel_tolerance),
            isclose(self.y.end, other.y.end, rel_tol=rel_tolerance),
            ])


class BoundingBox(NormalizedRectangle):

    def __init__(self, x1, y1, x2, y2, precision=3):
        self._precision = precision
        super(BoundingBox, self).__init__(
            round(x1, self._precision),
            round(y1, self._precision),
            round(x2 - x1, self._precision),
            round(y2 - y1, self._precision),
            )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(x={self.x.start}, y={self.y.start}, "
            f"width={self.x.size}, height={self.y.size}, precision={self._precision})"
            )

    def as_bounding_box_dict(self):
        return {
            'x': self.x.start,
            'y': self.y.start,
            'width': round(self.x.size, self._precision),
            'height': round(self.y.size, self._precision),
            }
