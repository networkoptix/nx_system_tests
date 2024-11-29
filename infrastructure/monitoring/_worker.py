# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from threading import Thread
from typing import Mapping
from typing import Optional
from typing import Sequence

from infrastructure._message import MessageBatchInput
from infrastructure.monitoring._task import _Task


class WorkerStateStore:

    def __init__(self, message_input: MessageBatchInput):
        self._message_input = message_input
        self._worker_states = {}
        self._thread = Thread(target=self._target, daemon=True, name='WorkerStateStoreThread')
        self._thread.start()

    def list(self) -> Mapping[str, Sequence['_WorkerState']]:
        result = {}
        for group, worker_id in sorted(self._worker_states.keys()):
            result.setdefault(group, []).append(self._worker_states[group, worker_id])
        return result

    def _target(self):
        try:
            while True:
                self._process_updates()
                time.sleep(5)
        except Exception:
            _logger.exception("WorkerStateStore thread failed")
            raise

    def _process_updates(self):
        # Worker states are stored in dict so subsequent worker state updates will rewrite
        # previous one and only latest update will appear in the result.
        new_messages = self._message_input.list_latest_messages()
        for message in new_messages:
            worker_state = _WorkerState(json.loads(message))
            self._worker_states[worker_state.group(), worker_state.id()] = worker_state


class _WorkerState:

    def __init__(self, worker_state_raw):
        self._raw = worker_state_raw

    def serialize(self):
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        seconds_since_last_update = (now - self.updated_at()).total_seconds()
        state = self._state(seconds_since_last_update)
        worker_data = {
            "id": self.id(),
            "status": {
                "class": state,
                'text': f"{state} ({self._status()})",
                },
            "seconds_since_last_update": f'{seconds_since_last_update:.0f}',
            }
        current_task = self._current_task()
        if current_task is not None:
            worker_data['task'] = current_task.serialize()
        return worker_data

    def _state(self, seconds_since_last_update):
        stuck_timeout_sec = 30 if self._status() == 'idle' else 3600
        dead_timeout_sec = 3 * stuck_timeout_sec
        gone_timeout_sec = 3 * dead_timeout_sec
        state = (
            'gone' if seconds_since_last_update > gone_timeout_sec else
            'dead' if seconds_since_last_update > dead_timeout_sec else
            'stuck' if seconds_since_last_update > stuck_timeout_sec else
            'alive'
            )
        return state

    @lru_cache(1)
    def group(self) -> str:
        return self._raw['task_group']

    @lru_cache(1)
    def id(self) -> str:
        return self._raw['worker_id']

    @lru_cache(1)
    def updated_at(self) -> datetime:
        return datetime.fromisoformat(self._raw['updated_at'])

    def _status(self) -> str:
        return self._raw['status']

    def _current_task(self) -> Optional['_Task']:
        if 'task' in self._raw:
            return _Task(self._raw['task'])
        else:
            return None


_logger = logging.getLogger(__name__)
