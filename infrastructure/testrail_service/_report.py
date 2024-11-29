# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from enum import IntEnum
from typing import Collection
from typing import NamedTuple

from infrastructure.testrail_service._ft_job import FTJobCollection
from infrastructure.testrail_service._testrail_api import TestrailRun
from infrastructure.testrail_service._tests_mapper import map_tests_to_jobs


def form_reports(ft_jobs: FTJobCollection, runs: Collection[TestrailRun], vms_info):
    result = {
        'run': [],
        'status': [
            {'id': int(_TestrailTestStatus.PASSED_AUTOTEST), 'meaning': 'passed'},
            {'id': int(_TestrailTestStatus.FAILED_AUTOTEST), 'meaning': 'failed'},
            ],
        'test': [],
        'reports': [],
        'mismatched_jobs': [],
        }
    mismatched_jobs = set(ft_jobs.list_all())
    for run in runs:
        mapping = map_tests_to_jobs(ft_jobs, run.list_tests())
        result['run'].append({
            'id': run.id(),
            'name': run.name(),
            'mismatched_tests': [test.id() for test in mapping.get_mismatched_testrail_tests()],
            })
        for test in run.list_tests():
            result['test'].append({
                'id': test.id(),
                **test.serialize(),
                })
        if mapping.get_matches():
            run_id = run.id()
            result['reports'].append(form_run_report(run_id, mapping.get_matches(), vms_info))
        mismatched_jobs &= set(mapping.get_mismatched_ft_jobs())
    for job in mismatched_jobs:
        result['mismatched_jobs'].append({
            'name': job.get_stage(),
            'url': job.get_history_url(),
            'stage_url': job.get_stage_url(),
            'status': job.get_status(),
            })
    return result


class VMSInfo(NamedTuple):
    url: str
    build: str


def form_run_report(run_id, matches, vms_info):
    results = []
    for testrail_test, ft_jobs in matches.items():
        all_jobs_passed = all(job.is_passed() for job in ft_jobs)
        comment = ''
        for job in ft_jobs:
            comment += _markdown_url(job.get_status(), job.get_history_url()) + ': '
            comment += _markdown_url(job.get_stage(), job.get_stage_url()) + '\n'
        comment += '\n' + _markdown_url('VMS Build', vms_info.url) + '\n'
        results.append({
            'test_id': testrail_test.id(),
            'status_id': int(
                _TestrailTestStatus.PASSED_AUTOTEST if all_jobs_passed else
                _TestrailTestStatus.FAILED_AUTOTEST),
            'comment': comment,
            'version': vms_info.build,
            })
    return {
        'run_id': run_id,
        'uri': f'/api/v2/add_results/{run_id}',
        'data': {'results': results},
        }


def _markdown_url(text, url):
    return f'[{text}]({url})'


class _TestrailTestStatus(IntEnum):
    PASSED_AUTOTEST = 7
    FAILED_AUTOTEST = 8
    _RETEST_AUTOTEST = 9
