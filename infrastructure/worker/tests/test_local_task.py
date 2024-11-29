# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from typing import Generator
from typing import Tuple

from infrastructure.worker._task import LocalTask
from infrastructure.worker._worker import CannotMakeLocalTask
from infrastructure.worker._worker import make_local_task


class LocalTaskScenarios(unittest.TestCase):

    def setUp(self):
        self._artifacts_root = Path(tempfile.mkdtemp(dir=str(Path('~/.cache/').expanduser())))
        self._stdout_file = (self._artifacts_root / 'stdout.txt')

    def test_success_task(self):
        script = Path(__file__).with_name('_success_script.py').read_text()
        task = LocalTask(script, ['python3', '-'], {})
        stdout_gen = task.run(Path(__file__).parent, self._artifacts_root, timeout_sec=1)
        [stdout, run_status] = _get_script_result(stdout_gen)
        expected_stdout_line = b'message to stdout'
        self.assertEqual(stdout.splitlines(), [expected_stdout_line])
        self.assertEqual(run_status, 'succeed')
        self.assertEqual(self._stdout_file.read_bytes().splitlines(), [expected_stdout_line])

    def test_failed_task(self):
        script = Path(__file__).with_name('_failure_script.py').read_text()
        task = LocalTask(script, ['python3', '-'], {})
        stdout_gen = task.run(Path(__file__).parent, self._artifacts_root, timeout_sec=1)
        [stdout, run_status] = _get_script_result(stdout_gen)
        expected_stdout_line = b'message to stdout'
        self.assertEqual(stdout.splitlines(), [expected_stdout_line])
        self.assertEqual(run_status, 'failed_with_code_11')
        self.assertEqual(self._stdout_file.read_bytes().splitlines(), [expected_stdout_line])

    def test_timeout_task(self):
        script = Path(__file__).with_name('_timeout_script.py').read_text()
        task = LocalTask(script, ['python3', '-'], {})
        stdout_gen = task.run(Path(__file__).parent, self._artifacts_root, timeout_sec=1)
        [stdout, run_status] = _get_script_result(stdout_gen)
        expected_stdout_line = b'message to stdout'
        self.assertTrue(expected_stdout_line in stdout.splitlines(), stdout)
        self.assertEqual(run_status, 'failed_timed_out')
        logged_stdout = self._stdout_file.read_bytes().splitlines()
        self.assertTrue(expected_stdout_line in logged_stdout, logged_stdout)

    def test_task_with_empty_script(self):
        task = LocalTask('', ['python3', '_success_script.py'], {})
        stdout_gen = task.run(Path(__file__).parent, self._artifacts_root, timeout_sec=1)
        [stdout, run_status] = _get_script_result(stdout_gen)
        expected_stdout_line = b'message to stdout'
        self.assertEqual(stdout.splitlines(), [expected_stdout_line])
        self.assertEqual(run_status, 'succeed')
        self.assertEqual(self._stdout_file.read_bytes().splitlines(), [expected_stdout_line])

    def tearDown(self):
        for _ in range(3):
            # Sometimes on Windows folder cannot be deleted because file is used by another process
            # which is actually already killed. Retry deletion in that case.
            try:
                shutil.rmtree(self._artifacts_root)
            except PermissionError:
                time.sleep(0.5)
            except FileNotFoundError:
                break


class TestMakeLocalTask(unittest.TestCase):

    def test_valid_task(self):
        make_local_task({
            'script': '',
            'args': ['python3', '-'],
            })

    def test_empty_task_raw(self):
        with self.assertRaisesRegex(CannotMakeLocalTask, r"\['args', 'script'\] fields are missing"):
            make_local_task({})

    def test_invalid_env_values(self):
        with self.assertRaisesRegex(CannotMakeLocalTask, "Environment can only contain strings"):
            make_local_task({
                'script': '',
                'args': ['python3', '-'],
                'env': {'': None},
                })

    def test_invalid_env_type(self):
        with self.assertRaisesRegex(CannotMakeLocalTask, "Environment must be a dict, got <class 'int'>"):
            make_local_task({
                'script': '',
                'args': ['python3', '-'],
                'env': 0,
                })


def _get_script_result(stdout_gen: Generator[bytes, None, str]) -> Tuple[bytes, str]:
    stdout = bytearray()
    while True:
        try:
            stdout += next(stdout_gen)
        except StopIteration as e:
            run_status = e.value
            break
    return stdout, run_status


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
