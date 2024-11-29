# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import unittest

from infrastructure.elasticsearch_logging import Buffer


class TestBuffer(unittest.TestCase):

    def test_basic(self):
        b = Buffer(2)
        b.append(b'qwe\n')
        self.assertFalse(b.too_much())
        b.append(b'asd\n')
        self.assertTrue(b.too_much())
        self.assertTrue(b.read_out())
        self.assertFalse(b.too_much())
        self.assertFalse(b.read_out())
