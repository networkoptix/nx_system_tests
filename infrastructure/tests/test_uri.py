# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import socket
import unittest
from pathlib import Path

from infrastructure._uri import get_group_uri
from infrastructure._uri import get_process_uri


class TestURI(unittest.TestCase):

    def test_ft_unit_absent(self):
        os.environ.pop('FT_UNIT_NAME', None)
        caller_name = Path(__file__).stem
        group_uri = get_group_uri()
        process_uri = get_process_uri()
        self.assertNotEqual(group_uri, process_uri)
        self.assertEqual(group_uri, f'//{socket.gethostname()}')
        self.assertEqual(process_uri, group_uri + f'/{caller_name}')

    def test_ft_unit_without_params(self):
        unit_name = 'test_unit'
        os.environ['FT_UNIT_NAME'] = unit_name
        group_uri = get_group_uri()
        process_uri = get_process_uri()
        self.assertNotEqual(group_uri, process_uri)
        self.assertEqual(group_uri, '//' + unit_name)
        self.assertEqual(process_uri, group_uri + f'/{socket.gethostname()}/{unit_name}')

    def test_ft_unit_with_params(self):
        unit_name = 'test_unit@param'
        os.environ['FT_UNIT_NAME'] = unit_name
        group_uri = get_group_uri()
        process_uri = get_process_uri()
        self.assertNotEqual(group_uri, process_uri)
        [common_name, _, _] = unit_name.partition('@')
        self.assertEqual(group_uri, '//' + common_name)
        self.assertEqual(process_uri, group_uri + f'/{socket.gethostname()}/{unit_name}')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
