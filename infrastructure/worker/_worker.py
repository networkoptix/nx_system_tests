# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import json
import logging
import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Mapping
from urllib.parse import urlparse

from directories import clean_up_artifacts
from directories import get_ft_artifacts_root
from infrastructure._message import MessageInput
from infrastructure._message import MessageOutput
from infrastructure.worker._task import LocalTask

_logger = logging.getLogger(__name__)


class Worker:

    def __init__(
            self,
            worker_uri: str,
            input_stream: MessageInput,
            output_stream: MessageOutput,
            worker_state_updates: MessageOutput,
            ):
        self._uri = worker_uri
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._state_updates = _WorkerStateUpdate(
            worker_state_updates, self._uri, self._input_stream.id())

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._uri}>"

    def run_single_task(self):
        _logger.info(
            "Worker %r started, task will be taken from %r, results will be reported to %r",
            self, self._input_stream, self._output_stream)
        with self._get_raw_task() as task_raw:
            if task_raw is None:
                _logger.info("Task queue is empty")
                self._state_updates.send_idle()
                return
            clean_up_artifacts()
            run_id = f"{datetime.utcnow():%Y%m%d%H%M%S%f}-{os.getpid()}"
            artifacts_root = _ArtifactsRoot(run_id)
            task_update = TaskUpdate(
                self._output_stream, task_raw, self._input_stream.id(), artifacts_root.url())
            try:
                local_task = make_local_task(task_raw)
            except CannotMakeLocalTask as e:
                error = f"Failed to make local task from {task_raw!r}: {e}"
                _logger.warning(error)
                worker_log = artifacts_root.path() / 'worker.log'
                worker_log.write_text(error)
                task_update.send_extraction_failed(self._uri)
                return
            task_update.send_running(self._uri)
            self._state_updates.send_running_task(task_raw, artifacts_root.url())
            stdout = local_task.run(self._run_dir(), artifacts_root.path(), timeout_sec=3600)
            while True:
                try:
                    chunk = next(stdout)
                except StopIteration as e:
                    run_status = e.value
                    break
                task_update.send_output(chunk)
            _logger.info("%r finished; result %s", local_task, run_status)
            task_update.send_finished(run_status)

    @contextmanager
    def _get_raw_task(self):
        message = self._input_stream.read_message()
        if message is not None:
            try:
                task_raw = json.loads(message)
            except ValueError as e:
                _logger.warning("Invalid message %s: %s", message, e)
                task_raw = None
            else:
                if not isinstance(task_raw, dict):
                    _logger.warning("Not a task: %s", message)
                    task_raw = None
        else:
            task_raw = None
        # On unhandled exception message must not be acknowledged.
        yield task_raw
        self._input_stream.acknowledge()

    @lru_cache(1)
    def _run_dir(self) -> Path:
        common_cache = Path('~/.cache/').expanduser()
        common_cache.mkdir(exist_ok=True)
        run_dir = common_cache / f'{urlparse(self._uri).path.strip("/")}'
        run_dir.mkdir(exist_ok=True, parents=True)
        return run_dir


class _ArtifactsRoot:
    _artifacts_root_absolute_path = get_ft_artifacts_root() / 'task-artifacts'
    _artifacts_root_relative_path = _artifacts_root_absolute_path.relative_to(Path('~/').expanduser())
    _artifacts_root_absolute_path.mkdir(exist_ok=True)
    _shared_logs_url = f'http://{socket.gethostname()}/~{getpass.getuser()}/{_artifacts_root_relative_path.as_posix()}/'

    def __init__(self, run_id: str):
        self._run_id = 'run-' + run_id

    @lru_cache(1)
    def url(self) -> str:
        return self._shared_logs_url + self._run_id

    @lru_cache(1)
    def path(self) -> Path:
        path = self._artifacts_root_absolute_path / self._run_id
        path.mkdir()
        return path


class CannotMakeLocalTask(Exception):
    pass


class _WorkerStateUpdate:

    def __init__(self, message_output: MessageOutput, worker_id: str, task_group: str):
        self._message_output = message_output
        self._worker_id = worker_id
        self._task_group = task_group

    def send_idle(self):
        self._message_output.write_message(json.dumps({
            'worker_id': self._worker_id,
            'task_group': self._task_group,
            'status': 'idle',
            'updated_at': datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='microseconds'),
            }))

    def send_running_task(self, task_raw: Mapping[str, Any], task_artifacts_url: str):
        self._message_output.write_message(json.dumps({
            'task': {**task_raw, 'task_artifacts_url': task_artifacts_url},
            'worker_id': self._worker_id,
            'status': 'running_task',
            'task_group': self._task_group,
            'updated_at': datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='microseconds'),
            }))


class TaskUpdate:

    def __init__(
            self,
            message_output: MessageOutput,
            task_raw: Mapping[str, Any],
            task_group: str,
            task_artifacts_url: str,
            ):
        self._message_output = message_output
        self._task_raw = task_raw
        self._task_group = task_group
        self._task_artifacts_url = task_artifacts_url
        self._output_total_size_limit = 5 * 1024 * 1024
        self._output_chunk_size_limit = 64 * 1024
        self._output_total_size = 0
        self._output_buffer = bytearray()
        self._output_sent_at = float('-inf')
        self._output_update_interval = 5

    def send_output(self, output_raw: bytes):
        if self._output_total_size > self._output_total_size_limit:
            return
        self._output_buffer.extend(output_raw)
        if time.monotonic() - self._output_sent_at < self._output_update_interval:
            return
        cached_output_size = len(self._output_buffer)
        if self._output_total_size + cached_output_size > self._output_total_size_limit:
            _logger.debug("Output size limit exceeded. No more output updates will be sent")
            output_update = (
                b'WARNING: Task generates too much output. No more updates will be sent. '
                b'See full output in task artifacts')
        else:
            output_update = self._output_buffer
        self._send_output(output_update)
        self._output_buffer.clear()
        self._output_total_size += cached_output_size
        self._output_sent_at = time.monotonic()

    def send_extraction_failed(self, worker_id: str):
        self._message_output.write_message(json.dumps({
            **self._task_raw,
            'status': 'failed_to_parse_task',
            'task_group': self._task_group,
            'failed': True,
            'task_artifacts_url': self._task_artifacts_url,
            'worker_id': worker_id,
            }))

    def send_running(self, worker_id: str):
        self._message_output.write_message(json.dumps({
            **self._task_raw,
            'status': 'running',
            'task_group': self._task_group,
            'task_artifacts_url': self._task_artifacts_url,
            'worker_id': worker_id,
            }))

    def send_finished(self, run_status):
        if self._output_buffer:
            self._send_output(self._output_buffer)
            self._output_buffer.clear()
        self._message_output.write_message(json.dumps({
            **self._task_raw,
            'status': run_status,
            'task_group': self._task_group,
            'task_artifacts_url': self._task_artifacts_url,
            'failed': True if run_status.startswith('failed') else False,
            'succeed': True if run_status == 'succeed' else False,
            }))

    def _send_output(self, output_raw: bytes):
        self._message_output.write_message(json.dumps({
            **self._task_raw,
            'task_group': self._task_group,
            'output': self._truncate_output(output_raw).decode(errors='backslashreplace'),
            }))

    def _truncate_output(self, output_raw: bytes):
        if len(output_raw) > self._output_chunk_size_limit:
            truncated = output_raw[-self._output_chunk_size_limit:]
            result = b'WARNING: Output update is too big; showing truncated:\n...' + truncated
        else:
            result = output_raw
        return result


def make_local_task(task_raw) -> LocalTask:
    required_fields = {'script', 'args'}
    missing_fields = sorted(required_fields.difference(task_raw))
    if missing_fields:
        raise CannotMakeLocalTask(f"{missing_fields} fields are missing")
    env = task_raw.get('env', {})
    if not isinstance(env, dict):
        raise CannotMakeLocalTask(f"Environment must be a dict, got {type(env)}")
    if not all(isinstance(key, str) and isinstance(env[key], str) for key in env):
        raise CannotMakeLocalTask("Environment can only contain strings")
    return LocalTask(
        task_raw['script'],
        task_raw['args'],
        env,
        )
