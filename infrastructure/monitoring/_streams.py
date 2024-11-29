# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone
from typing import Mapping
from typing import Tuple

from infrastructure.message_broker import MessageBroker


class StreamStateStore:

    def __init__(self, message_broker: MessageBroker):
        self._message_broker = message_broker

    def list(self) -> Mapping[Tuple[str, str], '_StreamGroup']:
        result = {}
        streams_data = self._message_broker.list_streams()
        for stream, stream_raw_state in streams_data.items():
            for group in stream_raw_state:
                group_data = _StreamGroup(group)
                result[stream, group_data.name()] = group_data
        return result

    def get_message(self, stream_name: str, message_id: str):
        return self._message_broker.get_message(stream_name, message_id)


class _StreamGroup:

    def __init__(self, stream_state_raw):
        self._raw = stream_state_raw

    def serialize(self):
        return {
            'name': self.name(),
            'lag': self._lag(),
            'pel_count': self._pel_count(),
            }

    def name(self):
        return self._raw['name']

    def _lag(self):
        return self._raw['lag']

    def _pel_count(self):
        return self._raw['pel-count']

    def consumers(self):
        for consumer_data in self._raw['consumers']:
            mapped_consumer_data = dict(zip(consumer_data[::2], consumer_data[1::2]))
            yield _StreamConsumer(mapped_consumer_data)


class _StreamConsumer:

    def __init__(self, consumer_raw):
        self._raw = consumer_raw

    def serialize(self):
        now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
        return {
            'name': self._name(),
            'seconds_since_last_seen': int(now - self._seen_time()),
            'seconds_since_last_active': int(now - self._active_time()),
            }

    def _name(self):
        return self._raw['name']

    def _seen_time(self):
        return self._raw['seen-time'] / 1000

    def _active_time(self):
        return self._raw['active-time'] / 1000

    def pending(self):
        return [{'message_id': message[0]} for message in self._raw.get('pending', [])]
