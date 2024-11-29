# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from pathlib import Path

from directories.filelocker import AlreadyLocked
from directories.filelocker import try_locked


class TimestampFileRateLimit:

    def __init__(self, timestamp_file: Path):
        self._timestamp_file = timestamp_file
        self._lock_file = self._timestamp_file.with_suffix('.lock')
        self._run_period_sec = 600

    def run_is_allowed(self) -> bool:
        return time.time() - self._get_last_run_time() > self._run_period_sec

    def become_leader(self) -> float:
        try:
            with try_locked(self._lock_file):
                last_run_at = self._get_last_run_time()
                if time.time() - last_run_at < self._run_period_sec:
                    _logger.info("Failed to become a leader; same process is launched recently")
                    raise NotALeader()
                self._timestamp_file.write_text(str(time.time()))
        except AlreadyLocked:
            raise NotALeader()
        return last_run_at

    def _get_last_run_time(self) -> float:
        try:
            return float(self._timestamp_file.read_text())
        except (FileNotFoundError, ValueError):
            # run_is_allowed() calls _get_last_run_time() outside of file lock.
            # It can be called in separate process.
            # Reading file at the same time write occurs leads to ValueError.
            # File can be corrupted, in which case ValueError will be
            # raised as well. Handle ValueError and return valid timestamp.
            # In any case file content should be overwritten in
            # become_leader() call.
            return time.time() - self._run_period_sec - 5


class NotALeader(Exception):
    pass


_logger = logging.getLogger(__name__)
