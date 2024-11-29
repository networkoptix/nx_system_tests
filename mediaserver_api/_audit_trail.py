# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
import time
from datetime import datetime

from mediaserver_api._base_queue import BaseQueue
from mediaserver_api._base_queue import EventNotOccurred

_logger = logging.getLogger(__name__)


class AuditTrail(BaseQueue):
    """Event queue for `api/auditLog`."""

    def __init__(self, api, skip_initial_records=True):
        super().__init__()
        self._api = api
        if skip_initial_records:
            self.wait_for_sequence()

    class AuditRecord:

        def __init__(
                self, type, params, resources, created_time_sec, range_start_sec,
                range_end_sec):
            self.type = type
            self.params = params
            self.resources = resources
            self.created_time_sec = created_time_sec
            self.range_start_sec = range_start_sec
            self.range_end_sec = range_end_sec
            # range_end_sec may change over time so we exclude it from object's _identity
            self._identity = (
                self.type,
                self.params,
                self.resources,
                self.created_time_sec,
                self.range_start_sec)

        def __repr__(self):
            created = datetime.fromtimestamp(self.created_time_sec)
            return (
                f"<AuditRecord "
                f"{created:%Y-%m-%d %H-%M-%S} "
                f"{self.type} "
                f"params={self.params!r} "
                f"resources={self.resources!r}>")

        def __hash__(self):
            return hash(self._identity)

        def __eq__(self, other_record):
            if not isinstance(other_record, type(self)):
                return NotImplemented
            return self._identity == other_record._identity

    def _load_events(self):
        return self._api.list_audit_trail_records()

    def _ensure_no_records_follow(self, timeout_sec=5):
        if timeout_sec > 0:
            try:
                unexpected_record = self.wait_for_next(timeout_sec=timeout_sec)
                # In case there are many unexpected events - log self._events
                _logger.debug("Got unexpected event(s): %s", self._events)
                raise RuntimeError(f"Got {unexpected_record}")
            except EventNotOccurred:
                pass

    def _make_record(self, record_data):
        # TODO: Get rid of this method, _load_events can do all work
        return record_data

    def wait_for_next(self, timeout_sec: float = 30):
        return super().wait_for_next(timeout_sec=timeout_sec)

    def wait_for_one(self, timeout_sec=30, silence_after_sec=5):
        start = time.monotonic()
        record = self.wait_for_next(timeout_sec=timeout_sec)

        while record.type in [
            self._api.audit_trail_events.LOGIN,
            self._api.audit_trail_events.UNAUTHORIZED_LOGIN,
                ]:
            # Skip login record.
            record = self.wait_for_next(timeout_sec=timeout_sec - time.monotonic() + start)

        self._ensure_no_records_follow(timeout_sec=silence_after_sec)
        return record

    def wait_for_sequence(self):
        sequence_timeout_sec = 6
        watchdog_timeout = 10
        # Wait for the first record in sequence
        sequence = [self.wait_for_one(silence_after_sec=0)]
        start = time.monotonic()

        while time.monotonic() - start < watchdog_timeout:
            try:
                sequence.append(self.wait_for_one(
                    timeout_sec=sequence_timeout_sec,
                    silence_after_sec=0))
            except EventNotOccurred:
                self._ensure_no_records_follow()
                return sequence

        else:
            raise RuntimeError(
                f"New records were constantly added to AuditTrail for {watchdog_timeout} seconds")
