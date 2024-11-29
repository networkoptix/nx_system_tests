# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import tempfile
import unittest
from pathlib import Path

from arms.ptftp._endpoints_registry import FileEndpointsRegistry
from arms.ptftp._endpoints_registry import TFTPPathNotFound


class TestDirectoryEndpointsRegistry(unittest.TestCase):

    def setUp(self):
        self._temp_dir = Path(tempfile.mkdtemp())

    def test_endpoint_not_found(self):
        registry = FileEndpointsRegistry(self._temp_dir)
        with self.assertRaises(TFTPPathNotFound):
            registry.find_root_path('1.1.1.1')

    def test_get_existing_endpoint(self):
        registry = FileEndpointsRegistry(self._temp_dir)
        ip = '192.168.1.1'
        expected_path = Path('/irrelevant')
        (self._temp_dir / ip).write_text(str(expected_path))
        received_path = registry.find_root_path(ip)
        self.assertEqual(received_path, expected_path)

    def test_bypass_unparseable_name(self):
        registry = FileEndpointsRegistry(self._temp_dir)
        (self._temp_dir / 'unparseable_as_ip').write_text(str(Path('/irrelevant')))
        with self.assertRaises(TFTPPathNotFound):
            registry.find_root_path('1.1.1.1')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
