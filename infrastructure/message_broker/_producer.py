# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from redis import Redis

from infrastructure._message import MessageOutput


class RedisProducer(MessageOutput):

    def __init__(self, redis: Redis, stream_name: str):
        self._redis = redis
        self._name = stream_name
        self._message_size_limit = 1 * 1024 * 1024

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._name}>"

    def write_message(self, message: str):
        size = len(message)
        if size > self._message_size_limit:
            raise RuntimeError(
                f"Refuse to send: message size {size / 1024 / 1024:.1f} MB"
                f"exceeds {self._message_size_limit / 1024 / 1024:.1f} MB")
        self._redis.xadd(self._name, fields={'message_body': message}, maxlen=1_000_000)

    def is_alive(self) -> bool:
        try:
            self._redis.ping()
        except ConnectionError:
            return False
        return True

    def id(self):
        return self._name
