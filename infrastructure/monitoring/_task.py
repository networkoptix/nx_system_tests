# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from collections import OrderedDict
from functools import lru_cache
from threading import Thread
from typing import Mapping
from typing import Optional
from typing import Sequence
from urllib.parse import urlparse
from uuid import uuid1

from infrastructure._message import MessageBatchInput


class TaskStore:

    def __init__(self, *message_inputs: MessageBatchInput):
        self._message_inputs = message_inputs
        self._store = OrderedDict({})
        self._thread = Thread(target=self._target, daemon=True, name='TaskStoreThread')
        self._thread.start()

    def list(self) -> Mapping[str, Sequence['_Task']]:
        task_groups = {}
        for task_group, task_id in sorted(self._store, reverse=True):
            try:
                task = self._store[task_group, task_id]
            except KeyError:
                continue
            task_groups.setdefault(task_group, []).append(task)
        return task_groups

    def _target(self):
        try:
            while True:
                self._process_updates()
                time.sleep(5)
        except Exception:
            _logger.exception("TaskStore thread failed")
            raise

    def _process_updates(self):
        for message_input in self._message_inputs:
            new_messages = message_input.list_latest_messages()
            for message in new_messages:
                task_raw = json.loads(message)
                if 'status' not in task_raw:
                    continue
                task = _Task(task_raw)
                if task.group() is None:
                    _logger.debug("Task %s group is absent, skip task", task.id())
                    continue
                # Tasks are stored in dict so subsequent task updates will rewrite
                # previous one and only latest update will appear in result.
                self._store[task.group(), task.id()] = task
                if len(self._store) > 80000:
                    self._store.popitem(last=False)


class _Task:

    def __init__(self, task_raw):
        self._raw = task_raw

    def serialize(self):
        task_data = {
            "id": '-'.join([self.source(), self.id()]),
            'status':
                {
                    'class': 'running' if self._status() == 'running' else '',
                    'text': self._status(),
                    },
            "script_args": self._formatted_args(),
            }
        artifacts_url = self._artifacts_url()
        if artifacts_url is not None:
            task_data["artifacts"] = {
                "href": artifacts_url,
                "url": urlparse(artifacts_url).netloc,
                }
        return task_data

    def _formatted_args(self):
        try:
            # run_from_git.py arguments
            [python, script, gitlab_repo_url, sha, *rest] = self._args()
        except ValueError:
            return json.dumps(self._args(), indent=2) + '\n' + json.dumps(self._env(), indent=2)
        else:
            formatted_args = '[\n'
            formatted_args += '  ' + json.dumps([python, script, gitlab_repo_url, sha])[1:-1] + ',\n'
            formatted_args += json.dumps(rest, indent=2)[2:-2]
            formatted_args += '\n]'
            formatted_args += '\n' + json.dumps(self._env(), indent=2)
            return formatted_args

    def group(self) -> Optional[str]:
        return self._raw.get('task_group')

    @lru_cache(1)
    def id(self) -> str:
        return self._env().get('FT_JOB_ID', str(uuid1()))

    def source(self) -> str:
        return self._env().get('FT_JOB_SOURCE', '')

    def _status(self) -> str:
        return self._raw.get('status', '')

    def _args(self) -> Sequence[str]:
        return self._raw['args']

    def _artifacts_url(self) -> Optional[str]:
        return self._raw.get('task_artifacts_url')

    def _env(self) -> Mapping[str, str]:
        return self._raw.get('env', {})


_logger = logging.getLogger(__name__)
