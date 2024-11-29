# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import random
import string
import time
import unittest

from infrastructure._message import MessageOutput
from infrastructure.worker._worker import TaskUpdate


class TestTaskUpdate(unittest.TestCase):

    def setUp(self):
        self._message_output = _FakeMessageOutput('test_output')
        self._task_update = TaskUpdate(self._message_output, {}, 'fake_task', 'https://fake_url.nxft.dev')

    def test_output_rate_limit(self):
        update_interval = 0.3
        self._task_update._output_update_interval = update_interval
        self._task_update.send_output(b'1;')
        self._task_update.send_output(b'2;')
        self._task_update.send_output(b'3;')
        self.assertEqual('1;', json.loads(self._message_output.pop_message())['output'])
        time.sleep(update_interval + 0.1)
        self._task_update.send_output(b'4;')
        self._task_update.send_output(b'5;')
        self._task_update.send_output(b'6;')
        self.assertEqual('2;3;4;', json.loads(self._message_output.pop_message())['output'])
        self._task_update.send_finished('succeed')
        self.assertEqual('5;6;', json.loads(self._message_output.pop_message())['output'])
        self.assertEqual('succeed', json.loads(self._message_output.pop_message())['status'])

    def test_output_size_limit(self):
        self._task_update._output_update_interval = 0
        chunk_size_limit = 200
        self._task_update._output_chunk_size_limit = chunk_size_limit
        self._task_update._output_total_size_limit = chunk_size_limit * 3
        chunk = _raw_chunk(chunk_size_limit * 2)
        self._task_update.send_output(chunk)
        self.assertEqual(
            f'WARNING: Output update is too big; showing truncated:\n...{chunk.decode()[-chunk_size_limit:]}',
            json.loads(self._message_output.pop_message())['output'])
        self._task_update.send_output(b'2')
        self.assertEqual('2', json.loads(self._message_output.pop_message())['output'])
        self._task_update.send_output(b'3' * chunk_size_limit)
        self.assertEqual(
            'WARNING: Task generates too much output. No more updates will be sent. See full output in task artifacts',
            json.loads(self._message_output.pop_message())['output'])
        self._task_update.send_output(b'4')
        self.assertRaises(_Empty, self._message_output.pop_message)
        self._task_update.send_finished('succeed')
        self.assertEqual('succeed', json.loads(self._message_output.pop_message())['status'])


class _FakeMessageOutput(MessageOutput):

    def __init__(self, name: str):
        self._name = name
        self._messages = []

    def write_message(self, message: str):
        self._messages.append(message)

    def is_alive(self):
        return True

    def id(self):
        return self._name

    def pop_message(self):
        try:
            return self._messages.pop(0)
        except IndexError:
            raise _Empty()


class _Empty(Exception):
    pass


def _raw_chunk(size: int) -> bytes:
    chunk = ''.join(random.choice(string.ascii_letters) for _ in range(size))
    return chunk.encode()
