# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping
from typing import NamedTuple

from mediaserver_api.analytics import BoundingBox
from tests.analytics.helpers.trajectory import Speed
from tests.analytics.helpers.trajectory import TrajectoryWithReflections


class Track:

    def __init__(
            self,
            start_frame_number: int,
            end_frame_number: int,
            type_id: str,
            attributes: Mapping[str, str],
            speed: Speed,
            init_bounding_box: BoundingBox,
            ):
        self.type_id = type_id
        self.attributes = attributes
        self.frame_attributes = _make_frame_attributes(
            init_bounding_box, start_frame_number, end_frame_number, speed)


class _FrameAttributes(NamedTuple):

    frame_number: int
    bounding_box: BoundingBox


def _make_frame_attributes(init_bounding_box, start_frame_number, end_frame_number, speed):
    trajectory = TrajectoryWithReflections(
        init_bounding_box=init_bounding_box,
        speed=speed,
        points_count=end_frame_number - start_frame_number + 1,
        )
    result = []
    for frame_number, point in enumerate(trajectory.points, start=start_frame_number):
        result.append(
            _FrameAttributes(
                frame_number=frame_number,
                bounding_box=BoundingBox(
                    x1=point.x,
                    y1=point.y,
                    x2=point.x + init_bounding_box.x.size,
                    y2=point.y + init_bounding_box.y.size,
                    ),
                ),
            )
    return result
