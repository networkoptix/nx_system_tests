# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import unittest
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from infrastructure.build_registry._app import make_app
from infrastructure.build_registry.tests._runtime_database import RuntimeDatabase


class TestRegistryHTTP(unittest.TestCase):

    def setUp(self):
        self.metadata_6_0_0_ubuntu18 = Path(__file__).with_name('metadata_6.0.0_ubuntu18.txt').read_text()
        self.metadata_5_0_0_win10 = Path(__file__).with_name('metadata_5.0.0_win10.txt').read_text()
        self.metadata_5_0_0_ubuntu20 = Path(__file__).with_name('metadata_5.0.0_ubuntu20.txt').read_text()
        self.metadata_6_0_0_win2019 = Path(__file__).with_name('metadata_6.0.0_win2019.txt').read_text()
        self.last_usage_db = RuntimeDatabase()
        self._fill_db()
        app = make_app(self.last_usage_db)
        self.server = HTTPServer(('127.0.0.1', 0), app)
        listen_host, listen_port = self.server.server_address
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.root_url = f'http://{listen_host}:{listen_port}'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=10)
        # HTTPServer does not wait its socket closure
        # what may lead to AddressAlreadyInUse error at the next test
        self.server.socket.close()

    def _fill_db(self):
        self.last_usage_db.add_build(self.metadata_6_0_0_ubuntu18)
        self.last_usage_db.add_build(self.metadata_5_0_0_win10)
        self.last_usage_db.add_build(self.metadata_5_0_0_ubuntu20)

    def test_invalid_query(self):
        with self.assertRaises(HTTPError):
            urlopen(f'{self.root_url}/builds?invalid=')

    def test_get_all_records(self):
        with urlopen(f'{self.root_url}/builds') as response:
            data = response.read().decode('utf-8')
        result = json.loads(data)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)
        self.assertEqual(result[2], self.metadata_6_0_0_ubuntu18)

    def test_get_record_by_url(self):
        query = urlencode({'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/*'})
        with urlopen(f'{self.root_url}/builds?{query}') as response:
            data = response.read().decode('utf-8')
        result = json.loads(data)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)

    def test_get_record_by_arch(self):
        query = urlencode({'ft:arch': 'x64'})
        with urlopen(f'{self.root_url}/builds?{query}') as response:
            data = response.read().decode('utf-8')
        result = json.loads(data)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)
        self.assertEqual(result[2], self.metadata_6_0_0_ubuntu18)

    def test_get_record_by_url_and_os_name(self):
        query = urlencode({'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/*', 'ft:os_name': 'ubuntu20'})
        with urlopen(f'{self.root_url}/builds?{query}') as response:
            data = response.read().decode('utf-8')
        result = json.loads(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)

    def test_add_record(self):
        request = Request(
            url=f'{self.root_url}/builds',
            method='POST',
            data=self.metadata_6_0_0_win2019.encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        urlopen(request)
        response = urlopen(f'{self.root_url}/builds')
        result = json.loads(response.read().decode('utf-8'))
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], self.metadata_6_0_0_win2019)
        query = urlencode({'ft:url': 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop*'})
        second_response = urlopen(f'{self.root_url}/builds?{query}')
        second_result = json.loads(second_response.read().decode('utf-8'))
        self.assertEqual(len(second_result), 2)
        self.assertEqual(second_result[0], self.metadata_6_0_0_win2019)
