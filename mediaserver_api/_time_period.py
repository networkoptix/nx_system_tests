# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import os
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional
from typing import Sequence


class TimePeriod:

    def __init__(self, start_ms: int, duration_ms: Optional[int] = None):
        self.start_ms = start_ms
        self.start = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
        if duration_ms is None:
            self.complete = False
        else:
            self.complete = True
            self._duration_ms = duration_ms
            self._duration_timedelta = timedelta(milliseconds=duration_ms)
            self.duration_sec = self._duration_timedelta.total_seconds()
            self.end_ms = self.start_ms + self._duration_ms
            self.end = self.start + self._duration_timedelta

    def __repr__(self):
        duration = f'duration_ms={self._duration_ms}' if self.complete else 'incomplete'
        return f'TimePeriod(start_ms={self.start_ms}, {duration})'

    def __eq__(self, other):
        if not isinstance(other, TimePeriod):
            return NotImplemented
        if self.start_ms != other.start_ms:
            return False
        if not self.complete and not other.complete:
            return True
        if not self.complete or not other.complete:
            return False
        return self._duration_ms == other._duration_ms

    def __hash__(self):
        if not self.complete:
            return hash(self.start_ms)
        return hash((self.start_ms, self._duration_ms))

    @classmethod
    def _from_filename(cls, filename):
        [stem, _] = os.path.splitext(filename)
        try:
            [start_ms_str, duration_ms_str] = stem.split('_')
        except ValueError:  # Incomplete time period
            start_ms_str = stem
            duration_ms = None
        else:
            duration_ms = int(duration_ms_str)
        return cls(int(start_ms_str), duration_ms)

    def join(self, other):
        if not isinstance(other, TimePeriod):
            raise TypeError(f"Cannot concatenate TimePeriod with {type(other)}")
        if not other.complete:
            duration_ms = None
        else:
            duration_ms = self._duration_ms + other._duration_ms
        return TimePeriod(self.start_ms, duration_ms)

    def is_among(self, periods_list, tolerance_sec=1):
        trimmed = self.trim_left(tolerance_sec * 1000).trim_right(tolerance_sec * 1000)
        return any([period.contains(trimmed) for period in periods_list])

    @staticmethod
    def consolidate(periods_list, tolerance_sec=0) -> Sequence[TimePeriod]:
        tolerance = timedelta(seconds=tolerance_sec)
        try:
            [first, *others] = periods_list
        except ValueError:
            return []
        consolidated = [first]
        for period in others:
            gap_length = period.start - consolidated[-1].end
            if gap_length <= tolerance:
                consolidated[-1] = consolidated[-1].extend(gap_length).join(period)
            else:
                consolidated.append(period)
        return consolidated

    @classmethod
    def list_from_filenames(cls, filename_list):
        chunk_periods = [cls._from_filename(filename) for filename in filename_list]
        return cls.consolidate(chunk_periods)

    def extend(self, delta: timedelta):
        if not self.complete:
            raise RuntimeError("Can't extend incomplete period")
        delta_ms = int(delta.total_seconds() * 1000)
        return TimePeriod(self.start_ms, self._duration_ms + delta_ms)

    @staticmethod
    def calculate_gaps(periods_list):
        gaps_list = []
        for previous, current in zip(periods_list, periods_list[1:]):
            gap_timedelta = current.start - previous.end
            gaps_list.append(gap_timedelta.total_seconds())
        return gaps_list

    @classmethod
    def from_datetime(cls, start: datetime, duration: Optional[timedelta] = None):
        start_ms = int(start.timestamp() * 1000)
        if duration is None:
            duration_ms = None
        else:
            duration_ms = int(duration.total_seconds() * 1000)
        return TimePeriod(start_ms, duration_ms)

    @classmethod
    def from_start_and_end_ms(cls, start_ms, end_ms):
        return cls(start_ms=start_ms, duration_ms=end_ms - start_ms)

    def trim_right(self, ms: int) -> TimePeriod:
        if not self.complete:
            raise RuntimeError("Non-finished time period could not be shrank")
        if ms > self._duration_ms:
            return TimePeriod(start_ms=self.start_ms, duration_ms=0)
        return TimePeriod(self.start_ms, self._duration_ms - ms)

    def trim_left(self, ms: int) -> TimePeriod:
        if not self.complete:
            return TimePeriod(start_ms=self.start_ms + ms, duration_ms=None)
        if ms > self._duration_ms:
            return TimePeriod(start_ms=self.start_ms + self._duration_ms, duration_ms=0)
        return TimePeriod(start_ms=self.start_ms + ms, duration_ms=self._duration_ms - ms)

    def contains(self, other: TimePeriod) -> bool:
        if not self.complete:
            raise RuntimeError(f"Non-finished {self} could not be compared")
        elif not other.complete:
            raise RuntimeError(f"Non-finished {other} could not be compared")
        if self.start_ms > other.start_ms:
            return False
        if self.end < other.end:
            return False
        return True
