# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections import deque

from redis import Redis

from infrastructure._message import MessageBatchInput


class RedisBatchReader(MessageBatchInput):

    def __init__(self, redis: Redis, stream: str, batch_size: int):
        self._redis = redis
        self._batch_size = batch_size
        self._cache = deque([], maxlen=batch_size)
        self._stream = stream
        self._read_until = '-'

    def list_latest_messages(self):
        latest_messages = self._redis.xrevrange(
            self._stream, '+', self._read_until, count=self._batch_size)
        for message_id, message in reversed(latest_messages):
            self._cache.append(message['message_body'])
            self._read_until = message_id
        return self._cache

    def id(self):
        return self._stream
