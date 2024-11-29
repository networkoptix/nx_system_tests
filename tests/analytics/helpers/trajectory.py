# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import NamedTuple

from mediaserver_api.analytics import BoundingBox
from mediaserver_api.analytics import Rectangle


class Speed(NamedTuple):

    dx: float
    dy: float


class Point:

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def move(self, speed: Speed):
        return Point(self.x + speed.dx, self.y + speed.dy)


class TrajectoryWithReflections:

    def __init__(
            self,
            init_bounding_box: BoundingBox,
            speed: Speed,
            points_count: int,
            ):
        self._init_point = Point(init_bounding_box.x.start, init_bounding_box.y.start)
        self._speed = speed
        self._area = Rectangle(
            x1=0,
            y1=0,
            x2=1 - init_bounding_box.x.size,
            y2=1 - init_bounding_box.y.size,
            )
        self._points_count = points_count
        self.points = self._make_trajectory_with_reflections()

    def _make_straight_trajectory(self):
        result = []
        point = self._init_point
        for _ in range(self._points_count):
            result.append(point)
            point = point.move(self._speed)
        return result

    def _make_trajectory_with_reflections(self):
        straight_points = self._make_straight_trajectory()
        result = []
        for point in straight_points:
            result.append(
                Point(
                    x=self._area.x.calc_rel_coordinate(point.x),
                    y=self._area.y.calc_rel_coordinate(point.y),
                    ))
        return result
