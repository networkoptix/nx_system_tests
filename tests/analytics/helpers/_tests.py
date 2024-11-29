# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import unittest

from mediaserver_api.analytics import BoundingBox
from tests.analytics.helpers.track import Track
from tests.analytics.helpers.trajectory import Speed

DELTA = 0.0001


class ObjectStreamGenerationTestCase(unittest.TestCase):

    def test_track(self):
        start_frame_number = 120
        end_frame_number = 180
        type_id = 'nx.base.Car'
        attributes = {
            'Color': 'White',
            'Brand': 'Toyota',
            }
        speed = Speed(0.03, 0.03)
        init_box = BoundingBox(0.2, 0.2, 0.4, 0.4)
        track = Track(
            start_frame_number=start_frame_number,
            end_frame_number=end_frame_number,
            type_id=type_id,
            attributes=attributes,
            speed=speed,
            init_bounding_box=init_box,
            )
        self.assertEqual(track.type_id, type_id)
        self.assertEqual(track.attributes, attributes)
        self.assertEqual(len(track.frame_attributes), end_frame_number - start_frame_number + 1)
        current_frame_number = start_frame_number
        for frame in track.frame_attributes:
            self.assertEqual(current_frame_number, frame.frame_number)
            box = frame.bounding_box
            # Bounding box fits in Rectangle(x1=0, y1=0, x2=1, y2=1)
            self.assertTrue(0 <= box.x.start <= 1)
            self.assertTrue(0 <= box.y.start <= 1)
            self.assertTrue(0 <= box.x.end <= 1)
            self.assertTrue(0 <= box.y.end <= 1)
            # Bounding box preserves its dimensions
            self.assertAlmostEqual(
                box.x.end - box.x.start, init_box.x.end - init_box.x.start, delta=DELTA)
            self.assertAlmostEqual(
                box.y.end - box.y.start, init_box.y.end - init_box.y.start, delta=DELTA)
            current_frame_number += 1
