# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

_logger = logging.getLogger(__name__)


class _PixelInterval:

    def __init__(self, start: float, length: float):
        self._start = start
        self._length = length

    def contains(self, other: '_PixelInterval') -> bool:
        self_end = self._start + self._length
        other_end = other._start + other._length
        return self._start <= other._start and other_end <= self_end

    def get_absolute_coordinate(self, start_relative: float) -> float:
        if not 0.0 <= start_relative <= 1.0:
            raise RuntimeError(f"Factor must fit between 0.0 and 1.0. Received: {start_relative}")
        return self._start + self._length * start_relative

    def __repr__(self):
        return f"{self.__class__.__name__}(start={self._start}, length={self._length})"


class BoundingRectangle:

    def __init__(self, x: float, y: float, width: float, height: float):
        self._width = _PixelInterval(x, width)
        self._height = _PixelInterval(y, height)
        _logger.debug("Create %r", self)

    def __repr__(self):
        return f'<{self.__class__.__name__}: width={self._width}, height={self._height}>'

    def contains(self, other: 'BoundingRectangle') -> bool:
        return self._width.contains(other._width) and self._height.contains(other._height)

    def get_absolute_coordinates(
            self,
            top_left_relative_width: float,
            top_left_relative_height: float,
            ) -> tuple[float, float]:
        absolute_x = self._width.get_absolute_coordinate(top_left_relative_width)
        absolute_y = self._height.get_absolute_coordinate(top_left_relative_height)
        return absolute_x, absolute_y
