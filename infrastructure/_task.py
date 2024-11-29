# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import TypedDict

from infrastructure._message import MessageOutput

_logger = logging.getLogger(__name__)


class TaskIngress:

    def __init__(
            self,
            task_input: 'TaskInput',
            task_output: MessageOutput,
            update_output: MessageOutput,
            ):
        self._task_input = task_input
        self._task_output = task_output
        self._updates_output = update_output
        self._task_requested_at = float('-inf')

    def process_one_task(self):
        request_interval_sec = 5
        if time.monotonic() - self._task_requested_at < request_interval_sec:
            return
        if not self._task_output.is_alive():
            # Do not acquire new task while task output is unavailable.
            _logger.warning("%s is dead, refuse to get new job", self._task_output)
            self._task_requested_at = time.monotonic()
            return
        task_message = self._task_input.request_new_task()
        if task_message is None:
            _logger.debug("Task input %s is empty", self._task_input)
            self._task_requested_at = time.monotonic()
            return
        updates_message = {
            **task_message,
            'task_group': self._task_output.id(),
            'status': 'enqueued',
            }
        task_message = json.dumps(task_message)
        updates_message = json.dumps(updates_message)
        _logger.info("Publish %s", task_message)
        self._task_output.write_message(task_message)
        self._updates_output.write_message(updates_message)


class TaskInput(metaclass=ABCMeta):

    @abstractmethod
    def request_new_task(self) -> 'Optional[SerializedTask]':
        pass


class SerializedTask(TypedDict):
    args: Sequence[str]
    script: str
    env: Mapping[str, str]
