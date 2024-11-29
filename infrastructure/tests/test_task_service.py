# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import unittest
from pathlib import Path

from infrastructure._task import TaskIngress
from infrastructure.tests._fake_task import make_fake_queue
from infrastructure.tests.test_ft_view_job_lifecycle import _FakeFTViewJobInput


class TestFTViewJobLifeCycle(unittest.TestCase):

    def test_job_to_task(self):
        task_output, _ = make_fake_queue('fake_tasks')
        update_output, _ = make_fake_queue('fake_updates')
        service = TaskIngress(
            _FakeFTViewJobInput(
                'git:fake',
                ),
            task_output,
            update_output,
            )
        service.process_one_task()
        self.assertDictEqual(task_output.peek_last_message(), {
            'script': Path(__file__, '../../../run_from_git.py').resolve().read_text(),
            'args': [
                'python3',
                '-',
                'git:fake',
                'stable',
                '-m',
                'run_single_test',
                '--installers-url=https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/master/36124/default/distrib/',
                ],
            'env': {
                'RUN_MACHINERY': 'http://sc-ft003:8050/batches-ft/',
                'FT_JOB_ID': '20231213150020831022',
                'FT_JOB_SOURCE': 'FTView',
                'BATCH_JOB_REVISION': 'stable',
                'BATCH_JOB_RUN_ID': '20231213150020831022',
                'BATCH_JOB_STAGE': 'run_single_test.py',
                'BATCH_JOB_VMS': 'https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/master/36124/default/distrib/',
                },
            })

    maxDiff = None
