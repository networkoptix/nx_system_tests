# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from typing import Collection
from typing import List
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from config import global_config

_ft_view_url = global_config['ft_view_url'].rstrip('/')


class FtJob:

    def __init__(self, ft_job_raw: dict):
        self._raw = ft_job_raw

    def is_passed(self) -> bool:
        return self.get_status() == "passed"

    def is_skipped(self) -> bool:
        return self.get_status() == "skipped"

    def get_status(self) -> str:
        return self._raw['status']

    def get_stage(self) -> str:
        return self._raw['cmdline']['args']

    def get_stage_url(self) -> str:
        return self._raw['source']

    def get_history_url(self) -> str:
        return _ft_view_url + self._raw['history_url']

    def get_testrail_case_ids(self) -> Collection[int]:
        result = []
        for mark in self._raw['other_tags']:
            mark: str
            if mark.startswith('testrail-'):
                mark = mark[9:]
            if mark.isdigit():
                result.append(int(mark))
        return result

    def tags_for_testrail_configs(self) -> List[str]:
        """Simpliest way to get parametrization tags from stage name.

        >>> FtJob({'cmdline': {'args': '-m tests.dir.test test_win11_v1'}}).tags_for_testrail_configs()
        ['test', 'win11', 'v1']
        >>> FtJob({'cmdline': {'args': '-m suites.gui.tests.test_main_window'}}).tags_for_testrail_configs()
        ['win11']
        >>> FtJob({'cmdline': {'args': '-m tests.cloud_portal.x_x test_some_feature'}}).tags_for_testrail_configs()
        ['chrome']
        """
        if self.get_stage().startswith('-m tests.gui.'):
            return ['win11']
        elif self.get_stage().startswith('-m tests.cloud_portal'):
            return ['chrome']
        _test, parametrization = self.get_stage().rsplit(' ', maxsplit=1)
        return parametrization.split('_')

    def __hash__(self):
        return hash(tuple(self._raw['cmdline'].items()))


def select_ft_jobs(vms_build_url, ft_revision_sha, tag='dir:tests/', machinery=global_config['ft_machinery_url']):
    query = urlencode(dict(vms=vms_build_url, revision=ft_revision_sha, tag=tag, machinery=machinery))
    request = Request(f'http://sc-ft003:8092/?{query}')
    _logger.debug("Requesting FT View for jobs: %r", query)
    with urlopen(request, timeout=10) as response:
        data = response.read()
    return FTJobCollection([FtJob(job) for job in json.loads(data)])


class FTJobCollection:

    def __init__(self, ft_jobs: Collection[FtJob]):
        self._all = [job for job in ft_jobs if not job.is_skipped()]
        self._case_id_to_jobs = {}
        for ft_job in self._all:
            for case_id in ft_job.get_testrail_case_ids():
                self._case_id_to_jobs.setdefault(case_id, []).append(ft_job)

    def list_by_case_id(self, case_id) -> Collection[FtJob]:
        return self._case_id_to_jobs.get(case_id, [])

    def list_all(self):
        return self._all


_logger = logging.getLogger(__name__)
