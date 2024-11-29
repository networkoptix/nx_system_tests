# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import unittest

from infrastructure.json_to_xml import json_to_xml


class TestJSONToXML(unittest.TestCase):

    def test_flat_dict(self):
        data = {'a': 1, 'b': 2, 'c': 3}
        expected_xml = '<root><a>1</a><b>2</b><c>3</c></root>'
        self.assertEqual(json_to_xml(data), expected_xml)

    def test_flat_list(self):
        data = [1, 2, 3]
        expected_xml = '<root><item>1</item><item>2</item><item>3</item></root>'
        self.assertEqual(json_to_xml(data), expected_xml)

    def test_number_as_key(self):
        data = {1: 1, 2: 2}
        self.assertRaises(TypeError, json_to_xml, data)

    def test_nested_dict(self):
        data = {'a': {'b': 1, 'c': 2}}
        expected_xml = '<root><a><b>1</b><c>2</c></a></root>'
        self.assertEqual(json_to_xml(data), expected_xml)

    def test_dict_with_simple_list(self):
        data = {'a': [1, 2]}
        expected_xml = '<root><a><item>1</item><item>2</item></a></root>'
        self.assertEqual(json_to_xml(data), expected_xml)

    def test_dict_with_nested_list(self):
        data = {'a': [{'b': 1, 'c': 2}, {'b': 1, 'c': 2}]}
        expected_xml = '<root><a><item><b>1</b><c>2</c></item><item><b>1</b><c>2</c></item></a></root>'
        self.assertEqual(json_to_xml(data), expected_xml)

    def test_dict_with_nested_lists(self):
        data = {'a': [[1, 2], [1, 2]]}
        expected_xml = '<root><a><item><item>1</item><item>2</item></item><item><item>1</item><item>2</item></item></a></root>'
        self.assertEqual(json_to_xml(data), expected_xml)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
