# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
import unittest

from real_camera_tests._expected_cameras import ExpectedCameras
from real_camera_tests._expected_cameras import expected_cameras_parent


class TestConfig(unittest.TestCase):

    def test_all_cameras(self):
        for d in self._configurations():
            with self.subTest(d.name):
                ExpectedCameras(d)

    def test_with_filter(self):
        for d in self._configurations():
            with self.subTest(d.name):
                filter_re = re.compile('DW.*|Hanwha.*', re.IGNORECASE)
                ExpectedCameras(d, camera_filter_re=filter_re)

    @staticmethod
    def _configurations():
        return [d for d in expected_cameras_parent.iterdir()]
