# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from typing import Mapping
from typing import Optional

from redis import Redis

from infrastructure._message import MessageInput
from infrastructure._message import MessageOutput
from infrastructure.message_broker._consumer import RedisConsumer
from infrastructure.message_broker._producer import RedisProducer
from infrastructure.message_broker._reader import RedisBatchReader


class MessageBroker:

    def __init__(self, host: str, username: str, password: str):
        self._redis = Redis(host=host, username=username, password=password, decode_responses=True)

    def get_producer(self, stream_name: str) -> 'MessageOutput':
        return RedisProducer(self._redis, stream_name)

    def get_consumer(
            self,
            stream_name: str,
            group_name: str,
            consumer_name: str,
            ) -> 'MessageInput':
        return RedisConsumer(
            self._redis,
            stream_name,
            group_name,
            consumer_name,
            )

    def list_streams(self):
        streams_data = {}
        for stream in self._redis.scan_iter(_type='STREAM', count=100):
            try:
                stream_state = self._redis.xinfo_stream(stream, full=True)
            except IndexError:
                continue
            else:
                streams_data[stream] = stream_state['groups']
        return streams_data

    def get_message(self, stream_name: str, message_id: str) -> Optional[Mapping]:
        if message := self._redis.xrange(stream_name, min=message_id, max=message_id):
            return json.loads(message[0][1]['message_body'])
        return None

    def get_batch_reader(self, stream: str, batch_size: int) -> RedisBatchReader:
        return RedisBatchReader(self._redis, stream, batch_size)

    def close(self):
        self._redis.close()
