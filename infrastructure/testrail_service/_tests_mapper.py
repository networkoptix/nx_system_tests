# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import List
from typing import Mapping
from typing import Sequence

from infrastructure.testrail_service._ft_job import FTJobCollection
from infrastructure.testrail_service._ft_job import FtJob
from infrastructure.testrail_service._strategies import get_strategy_registry
from infrastructure.testrail_service._testrail_api import TestrailTest


class _TestsMapper:
    # TODO: inline class to simple function

    def __init__(self, ft_jobs: FTJobCollection):
        self._ft_jobs = ft_jobs
        self._matches: dict[TestrailTest, List[FtJob]] = {}
        self._mismatched_testrail_tests: List[TestrailTest] = []
        self._mismatched_ft_jobs: List[FtJob] = [*ft_jobs.list_all()]

    def match_test(self, testrail_test: TestrailTest):
        strategies = get_strategy_registry()
        found_some = False
        for ft_job in self._ft_jobs.list_by_case_id(testrail_test.case_id()):
            job_tags = ft_job.tags_for_testrail_configs()
            configs = testrail_test.configs()
            all_matched = strategies.match_configs_and_tags(configs, job_tags)
            if all_matched:
                self._matches.setdefault(testrail_test, []).append(ft_job)
                if ft_job in self._mismatched_ft_jobs:
                    self._mismatched_ft_jobs.remove(ft_job)
                found_some = True
        if not found_some:
            self._mismatched_testrail_tests.append(testrail_test)

    def get_matches(self) -> Mapping[TestrailTest, Sequence[FtJob]]:
        return self._matches

    def get_mismatched_testrail_tests(self) -> Sequence[TestrailTest]:
        return self._mismatched_testrail_tests

    def get_mismatched_ft_jobs(self) -> Sequence[FtJob]:
        return self._mismatched_ft_jobs


def map_tests_to_jobs(ft_jobs, tests):
    tests_mapping = _TestsMapper(ft_jobs)
    for testrail_test in tests:
        tests_mapping.match_test(testrail_test)
    return tests_mapping
