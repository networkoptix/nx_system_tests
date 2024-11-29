# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.testrail_service._ft_job import FTJobCollection
from infrastructure.testrail_service._ft_job import FtJob
from infrastructure.testrail_service._report import VMSInfo
from infrastructure.testrail_service._report import form_run_report
from infrastructure.testrail_service._testrail_api import TestrailClient
from infrastructure.testrail_service._testrail_cache import CacheResponseDecorator
from infrastructure.testrail_service._testrail_cache import TestRailCache
from infrastructure.testrail_service._tests_mapper import map_tests_to_jobs

_test_data_dir = Path(__file__).parent.joinpath('test_data')
_jobs_path = _test_data_dir.joinpath('ft_jobs.json')
_cache_path = _test_data_dir.joinpath('testrail_cache.json')
_report_path = _test_data_dir.joinpath('testrail_report.json')


class TestCache(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_cache_writer(self):
        new_cache_path = self.tmp_path / 'testrail_cache.json'
        cached_api = TestRailCache(_cache_path)
        response_cacher = CacheResponseDecorator(cached_api)
        client = TestrailClient(response_cacher)
        client.get_run(8531)
        response_cacher.save(new_cache_path)
        cached_api = TestRailCache(new_cache_path)
        client = TestrailClient(cached_api)
        tests = client.get_run(8531).list_tests()
        self.assertEqual(len(tests), 13)
        self.assertEqual(_cache_path.read_text(), new_cache_path.read_text())


class TestPopulateTestrail(unittest.TestCase):

    maxDiff = 10000

    def test_mapping(self):
        cached_api = TestRailCache(_cache_path)
        testrail_client = TestrailClient(cached_api)
        ft_jobs = FTJobCollection([FtJob(job) for job in json.loads(_jobs_path.read_text())])
        tests = testrail_client.get_run(8531).list_tests()
        mapping = map_tests_to_jobs(ft_jobs, tests)
        matches = mapping.get_matches()
        mismatched_tests = mapping.get_mismatched_testrail_tests()
        mismatched_ft_jobs = mapping.get_mismatched_ft_jobs()
        [first_match, *_] = matches
        self.assertEqual(len(matches), 1)
        self.assertEqual(len(matches[first_match]), 2)
        self.assertEqual(len(mismatched_tests), 12)
        self.assertEqual(len(mismatched_ft_jobs), 1)

    def test_send_results(self):
        cached_api = TestRailCache(_cache_path)
        testrail_client = TestrailClient(cached_api)
        ft_jobs = FTJobCollection([FtJob(job) for job in json.loads(_jobs_path.read_text())])
        run = testrail_client.get_run(8531)
        mapping = map_tests_to_jobs(ft_jobs, run.list_tests())
        run_id = run.id()
        matches = mapping.get_matches()
        vms_url = 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/vms_6.0/608/default/distrib/'
        vms_info = VMSInfo(vms_url, "6.0.0.608 (926c4b745cde)")
        report = form_run_report(run_id, matches, vms_info)
        self.assertEqual(report, json.loads(_report_path.read_text()))
