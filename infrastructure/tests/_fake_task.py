# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from typing import Tuple

from infrastructure._message import MessageInput
from infrastructure._message import MessageOutput


def make_fake_queue(name) -> 'Tuple[_FakeMessageOutput, _FakeMessageInput]':
    queue = []
    return _FakeMessageOutput(name, queue), _FakeMessageInput(name, queue)


class _FakeMessageOutput(MessageOutput):

    def __init__(self, name: str, queue):
        self._name = name
        self._messages = queue

    def write_message(self, message: str):
        self._messages.append(message)

    def is_alive(self):
        return True

    def id(self):
        return self._name

    def peek_last_message(self):
        return json.loads(self._messages[-1])


class _FakeMessageInput(MessageInput):

    def __init__(self, name, queue):
        self._name = name
        self._messages = queue
        self._acknowledged = True

    def read_message(self):
        if not self._messages:
            return None
        if not self._acknowledged:
            raise RuntimeError("Not acknowledged")
        value = self._messages.pop(0)
        self._acknowledged = False
        return value

    def acknowledge(self):
        if self._acknowledged:
            raise RuntimeError("Already acknowledged")
        self._acknowledged = True

    def id(self):
        return self._name

    def shutdown(self):
        if not self._acknowledged:
            raise RuntimeError("Not acknowledged")
