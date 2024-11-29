# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection
from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from typing import Any

from mediaserver_api import MediaserverApi


class _EventQueue:

    def __init__(self, api: MediaserverApi, event_types: Collection[str]):
        self._api = api
        self._event_types = event_types
        self._queue = self._event_queue()

    def get_last_events(self) -> Sequence['_EventRecord']:
        return next(self._queue)

    def clear(self):
        next(self._queue)

    def _event_queue(self) -> Generator[Sequence['_EventRecord'], None, None]:
        last_timestamp = 0
        while True:
            events = []
            for event_type in self._event_types:
                for event_raw_data in self._api.list_events(type_=event_type):
                    one_event = self._build_event_record(event_raw_data)
                    if one_event.timestamp > last_timestamp:
                        events.append(one_event)
            events.sort(key=lambda e: e.timestamp)
            if events:
                last_timestamp = events[-1].timestamp
            _logger.debug('Events: %s', '\n'.join([r.as_str() for r in events]))
            yield events

    @staticmethod
    def _build_event_record(data: Mapping[str, Any]) -> '_EventRecord':
        if 'eventParams' in data:
            return _EventRecordV2(data)
        else:
            return _EventRecordV4(data)


class _EventRecord:
    def __init__(
            self,
            timestamp: int,
            event_type: str,
            reason_code: str | None,
            description: str | None,
            ):
        self.timestamp = timestamp
        self._event_type = event_type
        self._reason_code = reason_code
        self._description = description
        self._event_date = datetime.fromtimestamp(timestamp / 10**6, tz=timezone.utc)

    def as_str(self) -> str:
        if self._reason_code is None:
            return f'{self._event_date} {self._event_type}'
        else:
            return f'{self._event_date} {self._event_type} - {self._reason_code}({self._description})'


class _EventRecordV2(_EventRecord):

    def __init__(self, raw_data: Mapping[str, Any]):
        super().__init__(
            timestamp=int(raw_data['eventParams']['eventTimestampUsec']),
            event_type=raw_data["eventParams"]["eventType"],
            reason_code=raw_data['eventParams'].get('reasonCode'),
            description=raw_data['eventParams'].get('description'),
            )


class _EventRecordV4(_EventRecord):

    def __init__(self, raw_data: Mapping[str, Any]):
        super().__init__(
            timestamp=int(raw_data['eventData']['timestamp']),
            event_type=raw_data["eventData"]["type"],
            reason_code=raw_data['eventData'].get('reason'),
            description=raw_data['eventData'].get('reasonText'),
            )


_logger = logging.getLogger(__name__)
