# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import os
import unittest
from fnmatch import fnmatch
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from infrastructure._task import TaskIngress
from infrastructure._task_update import UpdateService
from infrastructure._uri import get_process_uri
from infrastructure.gitlab_job_requester import GitlabJobInput
from infrastructure.gitlab_job_requester import GitlabRunner
from infrastructure.gitlab_job_updater import GitlabJobReportFactory
from infrastructure.tests._fake_git import FakeGitRepo
from infrastructure.tests._fake_task import make_fake_queue
from infrastructure.worker import Worker


class GitlabJobLifeCycle(unittest.TestCase):

    def setUp(self):
        os.environ['FT_UNIT_NAME'] = 'test_worker@001'
        self.maxDiff = None
        self._fake_git_repo = FakeGitRepo()
        self._job = json.loads(Path(__file__).with_name('gitlab_job.json').read_text())
        self._task_stream = 'fake_tasks'
        self._task_output, self._task_input = make_fake_queue(self._task_stream)
        self._update_output, self._update_input = make_fake_queue('fake_updates')
        self._fake_gitlab = _FakeGitlab()
        self._task_ingress = TaskIngress(
            GitlabJobInput(
                GitlabRunner(self._fake_gitlab.url(), self._fake_gitlab.token_path()),
                self._fake_git_repo.uri()),
            self._task_output,
            self._update_output,
            )
        self._worker_state_update_output, _ = make_fake_queue('fake_workers')
        report_factory = GitlabJobReportFactory(self._fake_gitlab.url())
        self._update_service = UpdateService(self._update_input, report_factory)
        self._worker_uri = get_process_uri()
        self._worker = Worker(
            self._worker_uri, self._task_input, self._update_output, self._worker_state_update_output)

    def test_job_success_lifecycle(self):
        self._fake_git_repo.add_file_to_stable(
            'run_gitlab_job.py',
            Path(__file__).with_name('_success_script.py').read_text())
        self._task_ingress.process_one_task()
        task = self._task_output.peek_last_message()
        self.assertEqual(
            self._fake_gitlab.pop_trace(),
            "Job is taken by FT runner (runner id 1). See #ask-ft channel for help.\n")
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._update_service.process_one_update()
        self.assertEqual(self._fake_gitlab.pop_trace(), "status=enqueued\n")
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._worker.run_single_task()
        self._update_service.process_one_update()
        [status_line, worker_line, artifacts_line] = self._fake_gitlab.pop_trace().splitlines()
        self.assertEqual(status_line, "status=running")
        self.assertEqual(worker_line, f"worker_id={self._worker_uri}")
        self.assertTrue(artifacts_line.startswith("task_artifacts_url=http://"))
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._update_service.process_one_update()
        stdout_line = self._fake_gitlab.pop_trace()
        self.assertEqual("message to stdout", stdout_line.strip())
        self._update_service.process_one_update()
        [status_line, artifacts_line] = self._fake_gitlab.pop_trace().splitlines()
        self.assertEqual(status_line, "status=succeed")
        self.assertTrue(artifacts_line.startswith("task_artifacts_url=http://"))
        self.assertEqual(self._fake_gitlab.pop_state(), 'success')
        actual_update = self._worker_state_update_output.peek_last_message()
        self.assertTrue(actual_update['task']['task_artifacts_url'].startswith(('http://', 'https://')))
        self.assertEqual(actual_update['worker_id'], self._worker_uri)
        self.assertEqual(actual_update['status'], 'running_task')
        self.assertEqual(actual_update['task_group'], self._task_stream)
        self.assertDictEqual(actual_update['task'], {**actual_update['task'], **task})

    def test_job_failure_lifecycle(self):
        self._fake_git_repo.add_file_to_stable(
            'run_gitlab_job.py',
            Path(__file__).with_name('_failure_script.py').read_text())
        self._task_ingress.process_one_task()
        task = self._task_output.peek_last_message()
        self.assertEqual(
            self._fake_gitlab.pop_trace(),
            "Job is taken by FT runner (runner id 1). See #ask-ft channel for help.\n")
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._update_service.process_one_update()
        self.assertEqual(self._fake_gitlab.pop_trace(), "status=enqueued\n")
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._worker.run_single_task()
        self._update_service.process_one_update()
        [status_line, worker_line, artifacts_line] = self._fake_gitlab.pop_trace().splitlines()
        self.assertEqual(status_line, "status=running")
        self.assertEqual(worker_line, f"worker_id={self._worker_uri}")
        self.assertTrue(artifacts_line.startswith("task_artifacts_url=http://"))
        self.assertRaises(_Empty, self._fake_gitlab.pop_state)
        self._update_service.process_one_update()
        stdout_line = self._fake_gitlab.pop_trace()
        self.assertEqual("message to stdout", stdout_line.strip())
        self._update_service.process_one_update()
        [status_line, artifacts_line] = self._fake_gitlab.pop_trace().splitlines()
        self.assertEqual(status_line, "status=failed_with_code_11")
        self.assertTrue(artifacts_line.startswith("task_artifacts_url=http://"))
        self.assertEqual(self._fake_gitlab.pop_state(), 'failed')
        actual_update = self._worker_state_update_output.peek_last_message()
        self.assertTrue(actual_update['task']['task_artifacts_url'].startswith(('http://', 'https://')))
        self.assertEqual(actual_update['worker_id'], self._worker_uri)
        self.assertEqual(actual_update['status'], 'running_task')
        self.assertEqual(actual_update['task_group'], self._task_stream)
        self.assertDictEqual(actual_update['task'], {**actual_update['task'], **task})

    def tearDown(self):
        self._fake_git_repo.delete()
        self._task_input.shutdown()
        self._update_input.shutdown()


class _FakeGitlab:

    def __init__(self):
        self._handler_cls = _Handler
        self._server = HTTPServer(('127.0.0.1', 0), _Handler)
        self._thread = Thread(
            target=self._server.serve_forever,
            daemon=True,
            name='Thread-FakeFTView',
            )
        self._thread.start()

    def url(self) -> str:
        [host, port] = self._server.server_address
        return f'http://{host}:{port}'

    def token_path(self) -> str:
        token_path = Path('~/.cache/fake_runner_token.txt').expanduser()
        token_path.write_text('fake_token')
        return str(token_path)

    def pop_trace(self) -> str:
        return self._handler_cls.pop_trace()

    def pop_state(self) -> str:
        return self._handler_cls.pop_state()

    def close(self):
        self._server.shutdown()
        self._thread.join(timeout=10)
        self._server.server_close()


class _Handler(BaseHTTPRequestHandler):
    _trace_requests = []
    _range = 0
    _state_requests = []
    _job_raw = json.loads(Path(__file__).with_name('gitlab_job.json').read_bytes())

    @classmethod
    def pop_trace(cls) -> str:
        try:
            return cls._trace_requests.pop().decode('utf8')
        except IndexError:
            raise _Empty()

    @classmethod
    def pop_state(cls) -> str:
        try:
            return cls._state_requests.pop()
        except IndexError:
            raise _Empty()

    def do_POST(self):
        path = urlparse(self.path).path
        # Receive full request before client socket is closed.
        # If server responds just after request headers arrive,
        # request body may come late, after response is sent and
        # socket is already closed, causing a ConnectionAbortedError.
        _ = self._read_full()
        if path == '/api/v4/runners/verify':
            self._verify_runner()
        elif path == '/api/v4/jobs/request':
            self._send_job()
        else:
            self.send_error(404)

    def do_PATCH(self):
        path = urlparse(self.path).path
        # Receive full request before client socket is closed.
        # If server responds just after request headers arrive,
        # request body may come late, after response is sent and
        # socket is already closed, causing a ConnectionAbortedError.
        content = self._read_full()
        if fnmatch(path, '/api/v4/jobs/*/trace'):
            self._add_trace(content)
        else:
            self.send_error(404)

    def do_PUT(self):
        path = urlparse(self.path).path
        # Receive full request before client socket is closed.
        # If server responds just after request headers arrive,
        # request body may come late, after response is sent and
        # socket is already closed, causing a ConnectionAbortedError.
        content = self._read_full()
        if fnmatch(path, '/api/v4/jobs/*'):
            self._set_state(content)
        else:
            self.send_error(404)

    def _read_full(self) -> bytes:
        content_length = int(self.headers.get('Content-Length', '0'))
        return self.rfile.read(content_length)

    def _verify_runner(self):
        data = {'id': 1}
        data = json.dumps(data)
        data = data.encode('utf8')
        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_job(self):
        [host, port] = self.server.server_address
        api_v4_url = f'http://{host}:{port}/api/v4'
        # Override GitLab URL from job, use local fake GitLab HTTP server URL
        data = {
            **self._job_raw,
            'variables': [{'key': 'CI_API_V4_URL', 'value': api_v4_url}, *self._job_raw['variables']],
            }
        data = json.dumps(data)
        data = data.encode('utf8')
        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _add_trace(self, trace: bytes):
        self._range += len(trace)
        self._trace_requests.append(trace)
        self.send_response(202)
        # GitLab sends malformed header. The correct format is "bytes=0-123".
        self.send_header('Range', f'0-{self._range}')
        self.end_headers()

    def _set_state(self, update: bytes):
        self._state_requests.append(json.loads(update)['state'])
        self.send_response(200)
        self.end_headers()

    def log_message(self, message, *args):
        _logger.info("Fake GitLab HTTP server: " + message, *args)


class _Empty(Exception):
    pass


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
