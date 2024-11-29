# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.build_registry.builds_database import BuildsDatabase
from infrastructure.build_registry.builds_database import SqliteLastUsageDatabase
from infrastructure.build_registry.tests._runtime_database import RuntimeDatabase


class TestRegistry(unittest.TestCase):

    def setUp(self):
        self.metadata_6_0_0_ubuntu20 = Path(__file__).with_name('metadata_6.0.0_ubuntu20.txt').read_text()
        self.metadata_6_0_0_ubuntu18 = Path(__file__).with_name('metadata_6.0.0_ubuntu18.txt').read_text()
        self.metadata_5_0_0_win10 = Path(__file__).with_name('metadata_5.0.0_win10.txt').read_text()
        self.metadata_5_0_0_ubuntu20 = Path(__file__).with_name('metadata_5.0.0_ubuntu20.txt').read_text()
        self._database = self._setup_database()
        self._fill_db()

    def tearDown(self):
        self._database.close()
        self._cleanup_resources()

    def _fill_db(self):
        self._database.add_build(self.metadata_6_0_0_ubuntu20)
        self._database.add_build(self.metadata_6_0_0_ubuntu18)
        self._database.add_build(self.metadata_5_0_0_win10)
        self._database.add_build(self.metadata_5_0_0_ubuntu20)

    def _cleanup_resources(self):
        raise RuntimeError("_cleanup_resources() must be overridden in child class")

    def _setup_database(self) -> BuildsDatabase:
        raise RuntimeError("_setup_database() must be overridden in child class")

    def test_wrong_partial_query(self):
        result = self._database.full_text_search(metadata={'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/'})
        self.assertEqual(len(result), 0)

    def test_list_recent_db(self):
        result = self._database.list_recent()
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)
        self.assertEqual(result[2], self.metadata_6_0_0_ubuntu18)
        self.assertEqual(result[3], self.metadata_6_0_0_ubuntu20)

    def test_fts_by_url_with_distinctive_full_and_partial_results(self):
        [first_result] = self._database.full_text_search(metadata={
            'ft:url': 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/master/44332/default/distrib/',
            })
        self.assertEqual(first_result, self.metadata_6_0_0_ubuntu20)
        second_result = self._database.full_text_search(metadata={
            'ft:url': 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/*',
            })
        self.assertEqual(len(second_result), 2)
        self.assertEqual(second_result[0], self.metadata_6_0_0_ubuntu18)
        self.assertEqual(second_result[1], self.metadata_6_0_0_ubuntu20)

    def test_fts_by_url_with_same_full_and_partial_results(self):
        first_result = self._database.full_text_search(metadata={
            'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/vms_5.0_patch/5402/default/distrib/',
            })
        self.assertEqual(first_result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(first_result[1], self.metadata_5_0_0_win10)
        second_result = self._database.full_text_search(metadata={
            'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/*',
            })
        self.assertEqual(first_result, second_result)

    def test_get_record_by_arch(self):
        result = self._database.full_text_search(metadata={'ft:arch': 'x64'})
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)
        self.assertEqual(result[2], self.metadata_6_0_0_ubuntu18)
        self.assertEqual(result[3], self.metadata_6_0_0_ubuntu20)

    def test_get_record_by_url_and_os_name(self):
        result = self._database.full_text_search(metadata={
            'ft:url': 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/*',
            'ft:os_name': 'ubuntu20',
            })
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)


class TestSQLiteDatabase(TestRegistry):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tempdir = TemporaryDirectory()
        self._tempdir_root = Path(self._tempdir.name)

    def _setup_database(self):
        last_usage_db_path = self._tempdir_root / 'builds.db'
        return SqliteLastUsageDatabase(last_usage_db_path)

    def test_database_integrity(self):
        result = self._setup_database().list_recent()
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], self.metadata_5_0_0_ubuntu20)
        self.assertEqual(result[1], self.metadata_5_0_0_win10)
        self.assertEqual(result[2], self.metadata_6_0_0_ubuntu18)
        self.assertEqual(result[3], self.metadata_6_0_0_ubuntu20)

    def _cleanup_resources(self):
        self._tempdir.cleanup()


class TestRuntimeDatabase(TestRegistry):

    def _setup_database(self):
        return RuntimeDatabase()

    def _cleanup_resources(self):
        pass


def load_tests(loader, standard_tests, pattern):
    # Use load_tests() hook to skip base class
    # And load tests only from child test classes with database implementations.
    suite = unittest.TestSuite()
    for test_case in [TestSQLiteDatabase, TestRuntimeDatabase]:
        tests = loader.loadTestsFromTestCase(test_case)
        suite.addTest(tests)
    return suite
