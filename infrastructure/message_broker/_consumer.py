# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Optional
from typing import Tuple

from redis import Redis
from redis.exceptions import ResponseError

from infrastructure._message import MessageInput


class RedisConsumer(MessageInput):

    def __init__(
            self,
            redis: Redis,
            stream_name: str,
            group_name: str,
            consumer_name: str,
            ):
        self._redis = redis
        self._stream_name = stream_name
        self._group_name = group_name
        self._consumer_name = consumer_name
        self._current_message_id: Optional[str] = None
        try:
            # Consumer group will read messages that arrives after group creation. To force
            # consumers to read messages from specific offset use XGROUP SETID command.
            self._redis.xgroup_create(self._stream_name, self._group_name, mkstream=True, id='$')
        except ResponseError as e:
            if 'BUSYGROUP' not in str(e):
                raise

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"stream={self._stream_name} "
            f"group={self._group_name} "
            f"consumer={self._consumer_name}>"
            )

    def id(self):
        return self._stream_name

    def read_message(self):
        if self._current_message_id is not None:
            raise RuntimeError("Refuse to read new message: unacknowledged message exists")
        unacknowledged_message = self._get_unacknowledged_message()
        if unacknowledged_message is not None:
            [message_id, message_body] = unacknowledged_message
            self._current_message_id = message_id
            return message_body
        unprocessed_message = self._get_unprocessed_message()
        if unprocessed_message is not None:
            [message_id, message_body] = unprocessed_message
            self._current_message_id = message_id
            return message_body
        return None

    def acknowledge(self):
        if self._current_message_id is None:
            return
        self._redis.xack(self._stream_name, self._group_name, self._current_message_id)
        self._current_message_id = None

    def _get_unacknowledged_message(self) -> Optional[Tuple[str, str]]:
        response = self._redis.xreadgroup(
            self._group_name,
            self._consumer_name,
            streams={self._stream_name: '0-0'},
            block=5000,
            count=1,
            )
        [[_stream_id, messages]] = response
        if not messages:
            return None
        [[message_id, message_data]] = messages
        return message_id, message_data['message_body']

    def _get_unprocessed_message(self) -> Optional[Tuple[str, str]]:
        response = self._redis.xreadgroup(
            self._group_name,
            self._consumer_name,
            streams={self._stream_name: '>'},
            block=100,  # milliseconds
            count=1,
            )
        if not response:
            return None
        [[_stream_id, [[message_id, message_data]]]] = response
        return message_id, message_data['message_body']
