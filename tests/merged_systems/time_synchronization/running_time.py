# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
import math
import socket
import struct
import time
from datetime import datetime
from datetime import timezone
from typing import Tuple

from tests.waiting import wait_for_truthy


def wait_until_mediaserver_time_sync_with_internet(api, *, timeout_sec):
    wait_for_truthy(
        lambda: mediaserver_time_is_close_to_internet_time(api),
        description=f"time on {api} aligns with INTERNET TIME",
        timeout_sec=timeout_sec)


def mediaserver_time_is_close_to_internet_time(api):
    internet_time, internet_round_trip = _get_internet_time()
    started_at = time.monotonic()
    api_time = api.get_datetime().timestamp()
    round_trip = time.monotonic() - started_at
    extra_safety = 2
    total_tol = internet_round_trip + round_trip + extra_safety
    return math.isclose(api_time, internet_time, abs_tol=total_tol)


def wait_until_mediaserver_and_os_time_sync(api, os_access, *, timeout_sec: float):
    wait_for_truthy(
        lambda: mediaserver_and_os_time_are_in_sync(api, os_access),
        description=f"time on {api} follows time on {os_access}",
        timeout_sec=timeout_sec,
        )


def mediaserver_and_os_time_are_in_sync(api, os_access):
    started_at = time.monotonic()
    api_time = api.get_datetime().timestamp()
    os_time = os_access.get_datetime().timestamp()
    total_round_trip = time.monotonic() - started_at
    extra_safety = 2
    return math.isclose(api_time, os_time, abs_tol=total_round_trip + extra_safety)


def _get_internet_time(address='time.rfc868server.com', port=37) -> Tuple[float, float]:
    for _ in range(3):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            started_at = time.monotonic()
            try:
                s.connect((address, port))
            except (ConnectionError, TimeoutError) as e:
                _logger.debug("Connection to %s failed: %r", address, e)
                continue
            time_data = s.recv(4)
            request_duration = time.monotonic() - started_at
            break
    remote_as_posix_timestamp = _rfc868_to_unix(time_data)
    remote_as_datetime = datetime.fromtimestamp(remote_as_posix_timestamp, timezone.utc)
    _logger.debug(
        "Internet time %r, round trip %.3f",
        remote_as_datetime, request_duration)
    return remote_as_posix_timestamp, request_duration


def _rfc868_to_unix(raw: bytes) -> int:
    r"""Parse RFC868 time.

    >>> _rfc868_to_unix(b'\xe8\xff\x00\x00')
    1700036992
    """
    [rfc868_int] = struct.unpack('!I', raw)
    return rfc868_int - int(_rfc868_offset.total_seconds())


_rfc868_epoch = datetime(1900, 1, 1, tzinfo=timezone.utc)
_rfc868_offset = datetime.fromtimestamp(0, timezone.utc) - _rfc868_epoch

_logger = logging.getLogger(__name__)
