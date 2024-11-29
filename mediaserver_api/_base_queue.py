# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from pprint import pformat

_logger = logging.getLogger(__name__)


class BaseQueue(metaclass=ABCMeta):
    """Base class for Audit Trail and Events.

    Store and buffer events. Wait for a new event if nothing in buffer.

    Mediaserver doesn't contain event id in api/getEvents and api/auditLog.
    createdTimeSec is quite coarse - the second precision.
    """

    def __init__(self):
        self._events = []
        self._returned_event_count = 0

    @abstractmethod
    def _load_events(self):
        pass

    @abstractmethod
    def _make_record(self, record_data):
        return record_data

    def _reload_events(self):
        new_events = self._load_events()
        _logger.debug(
            'Loaded events:\n%s',
            pformat(new_events),
            )
        # Convert new events into named tuples list.
        new_events = [self._make_record(event) for event in new_events]

        for i, (old_event, new_event) in enumerate(zip(self._events, new_events)):
            if old_event != new_event:
                raise RuntimeError(
                    "Event sequence failure #{}: {} != {}".format(
                        i, old_event, new_event))
        self._events = new_events

    def wait_for_next(self, timeout_sec: float = 30):
        if self._returned_event_count == len(self._events):
            started_at = time.monotonic()

            while True:
                self._reload_events()

                if self._returned_event_count < len(self._events):
                    break

                if time.monotonic() > started_at + timeout_sec:
                    raise EventNotOccurred(
                        f"Timed out ({timeout_sec} seconds) waiting for event")

                time.sleep(1)

        event = self._events[self._returned_event_count]
        self._returned_event_count += 1
        return event

    def skip_existing_events(self):
        self._reload_events()
        self._returned_event_count = len(self._events)


class EventNotOccurred(Exception):
    pass
