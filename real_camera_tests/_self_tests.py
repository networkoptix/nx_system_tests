# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import unittest

from real_camera_tests._check_attributes import EqualTo
from real_camera_tests._check_attributes import ExpectedAttributes
from real_camera_tests._check_attributes import Vendor


class TestValueChecks(unittest.TestCase):

    def test_equal_to(self):
        checker = EqualTo('TEST')
        self.assertTrue(checker.compare('TEST'))
        self.assertFalse(checker.compare('TEST1'))
        checker = EqualTo(9)
        self.assertTrue(checker.compare(9))
        self.assertFalse(checker.compare(99))

    def test_vendor(self):
        checker = Vendor(['Hanwha Techwin', 'Hanwha Vision'])
        self.assertTrue(checker.compare('Hanwha Vision'))
        self.assertFalse(checker.compare('Hanwha AnyVision'))


class TestAttributesValidation(unittest.TestCase):

    def test_attributes_validator(self):
        checker = ExpectedAttributes({
            'vendor': Vendor(['Hanwha Techwin', 'Hanwha Vision']),
            'model': EqualTo('XND-6085V'),
            'mac': EqualTo('00-09-18-50-80-69'),
            'ptzCapabilities': EqualTo(0),
            })
        actual = {
            'vendor': 'Hanwha Vision',
            'model': 'XND-6085V',
            'mac': '00-09-18-50-80-69',
            'ptzCapabilities': 0,
            'test': 'TEST!',
            }
        self.assertEqual(len(checker.validate(actual)), 0)
        actual = {
            'vendor': 'Hanwha Vision X',
            'model': 'XND-6085V',
            'mac': '00-09-18-50-80-69',
            'ptzCapabilities': 0,
            'test': 'TEST!',
            }
        self.assertEqual(len(checker.validate(actual)), 1)
        actual = {
            'vendor': 'Hanwha Vision',
            'mac': '00-09-18-50-80-69',
            'ptzCapabilities': 0,
            'test': 'TEST!',
            }
        self.assertEqual(len(checker.validate(actual)), 1)
