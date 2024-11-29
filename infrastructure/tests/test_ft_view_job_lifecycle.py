# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import os
import re
import unittest
from pathlib import Path

from infrastructure._task import TaskIngress
from infrastructure._task import TaskInput
from infrastructure._task_update import UpdateReportFactory
from infrastructure._task_update import UpdateService
from infrastructure._uri import get_process_uri
from infrastructure.ft_view_job_requester._task import ft_task_db_to_redis
from infrastructure.ft_view_job_updater._update_serializarion import ft_view_update_serialize
from infrastructure.tests._fake_git import FakeGitRepo
from infrastructure.tests._fake_task import make_fake_queue
from infrastructure.worker import Worker


class TestFTViewJobLifeCycle(unittest.TestCase):

    def setUp(self):
        os.environ['FT_UNIT_NAME'] = 'test_worker@001'
        self.maxDiff = None
        self._fake_git_repo = FakeGitRepo()
        self._task_stream = 'fake_tasks'
        self._task_output, self._task_input = make_fake_queue(self._task_stream)
        self._update_output, self._update_input = make_fake_queue('fake_updates')
        self._update_output_factory = _FakeFTViewJobReportFactory()
        self._task_ingress = TaskIngress(
            _FakeFTViewJobInput(self._fake_git_repo.uri()),
            self._task_output,
            self._update_output,
            )
        self._worker_state_update_output, _ = make_fake_queue('fake_workers')
        self._update_service = UpdateService(self._update_input, self._update_output_factory)
        self._worker_uri = get_process_uri()
        self._worker = Worker(
            self._worker_uri, self._task_input, self._update_output, self._worker_state_update_output)

    def test_job_success_lifecycle(self):
        self._test_job_lifecycle('_success_script.py', 'succeed')

    def test_job_failure_lifecycle(self):
        self._test_job_lifecycle('_failure_script.py', 'failed_with_code_11')

    def _test_job_lifecycle(self, job_script: str, final_status: str):
        ft_view_job = _FakeFTViewJobInput.job
        self._fake_git_repo.add_file_to_stable(
            'run_single_test.py', Path(__file__).with_name(job_script).read_text())
        self._task_ingress.process_one_task()
        task = self._task_output.peek_last_message()
        self._update_service.process_one_update()
        actual_first_update_data = self._update_output_factory.store.pop()
        expected_first_update_data = {'status': 'enqueued', 'task_artifacts_url': None, **ft_view_job}
        self.assertEqual(actual_first_update_data, expected_first_update_data)
        self._worker.run_single_task()
        self._update_service.process_one_update()
        actual_second_update_data = self._update_output_factory.store.pop()
        self.assertRegex(actual_second_update_data['task_artifacts_url'], re.compile('^https?://'))
        self.assertDictEqual(
            actual_second_update_data,
            {**actual_second_update_data, 'status': 'running', **ft_view_job})
        self._update_service.process_one_update()
        self._update_output_factory.store.pop()  # Output update data
        self._update_service.process_one_update()
        actual_third_update_data = self._update_output_factory.store.pop()
        self.assertRegex(actual_third_update_data['task_artifacts_url'], re.compile('^https?://'))
        self.assertDictEqual(
            actual_third_update_data,
            {**actual_third_update_data, 'status': final_status, **ft_view_job})
        actual_worker_update = self._worker_state_update_output.peek_last_message()
        self.assertEqual(actual_worker_update['worker_id'], self._worker_uri)
        self.assertEqual(actual_worker_update['status'], 'running_task')
        self.assertEqual(actual_worker_update['task_group'], self._task_stream)
        self.assertRegex(actual_worker_update['task']['task_artifacts_url'], re.compile('^https?://'))
        self.assertDictEqual(actual_worker_update['task'], {**actual_worker_update['task'], **task})

    def tearDown(self):
        self._fake_git_repo.delete()
        self._task_input.shutdown()
        self._update_input.shutdown()


class _FakeFTViewJobInput(TaskInput):

    _job_raw = Path(__file__).with_name('ft_view_job.json').read_bytes()
    job = json.loads(_job_raw)

    def __init__(self, git_fetch_url):
        self._git_fetch_url = git_fetch_url

    def request_new_task(self):
        return ft_task_db_to_redis(self.job, self._git_fetch_url)


class _FakeFTViewJobReportFactory(UpdateReportFactory):

    def __init__(self):
        self.store = []

    def send_report(self, update_raw):
        serialized = ft_view_update_serialize(update_raw)
        self.store.append(serialized)


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
