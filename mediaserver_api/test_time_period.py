# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
import unittest

from mediaserver_api._time_period import TimePeriod


class TestTimePeriodContains(unittest.TestCase):

    def test_contains(self):
        now_ms = int(time.monotonic() * 1000)
        main_duration_ms = 10000
        backup_duration_ms = 9950
        duration_difference_ms = main_duration_ms - backup_duration_ms
        main_time_period = TimePeriod(now_ms, main_duration_ms)
        backup_time_period = TimePeriod(now_ms, backup_duration_ms)
        right_trimmed_period = main_time_period.trim_right(duration_difference_ms)
        self.assertTrue(backup_time_period.contains(right_trimmed_period))
        left_trimmed_period = main_time_period.trim_left(duration_difference_ms)
        self.assertTrue(main_time_period.contains(left_trimmed_period))
        left_right_trimmed_period = left_trimmed_period.trim_right(duration_difference_ms)
        self.assertTrue(backup_time_period.contains(left_right_trimmed_period))

    def test_not_contains(self):
        now_ms = int(time.monotonic() * 1000)
        main_duration_ms = 10000
        backup_duration_ms = 9950
        duration_difference_ms = main_duration_ms - backup_duration_ms
        main_time_period = TimePeriod(now_ms, main_duration_ms)
        backup_time_period = TimePeriod(now_ms, backup_duration_ms)
        right_trimmed_period = main_time_period.trim_right(duration_difference_ms + 10)
        self.assertFalse(right_trimmed_period.contains(backup_time_period))
        left_trimmed_period = main_time_period.trim_left(duration_difference_ms)
        self.assertFalse(backup_time_period.contains(left_trimmed_period))

    def test_not_finished_main_period(self):
        now_ms = int(time.monotonic() * 1000)
        main_time_period = TimePeriod(now_ms, None)
        backup_time_period = TimePeriod(now_ms, 10000)
        with self.assertRaises(RuntimeError):
            main_time_period.contains(backup_time_period)

    def test_not_finished_backup_period(self):
        now_ms = int(time.monotonic() * 1000)
        main_time_period = TimePeriod(now_ms, 10000)
        backup_time_period = TimePeriod(now_ms, None)
        with self.assertRaises(RuntimeError):
            main_time_period.contains(backup_time_period)

    def test_trim_left(self):
        now_ms = int(time.monotonic() * 1000)
        duration_ms = 10000
        main_period = TimePeriod(start_ms=now_ms, duration_ms=duration_ms)
        trimmed_left = main_period.trim_left(duration_ms // 2)
        self.assertTrue(trimmed_left.duration_sec * 1000 == duration_ms // 2)
        self.assertTrue(trimmed_left.start_ms == now_ms + duration_ms // 2)
        overtrimmed = main_period.trim_left(duration_ms * 2)
        self.assertTrue(overtrimmed.duration_sec == 0)
        self.assertTrue(overtrimmed.start_ms == now_ms + duration_ms)
        not_complete = TimePeriod(start_ms=now_ms, duration_ms=None)
        trimmed_not_complete = not_complete.trim_left(duration_ms)
        self.assertFalse(trimmed_not_complete.complete)
        self.assertTrue(trimmed_not_complete.start_ms == now_ms + duration_ms)

    def test_trim_right(self):
        now_ms = int(time.monotonic() * 1000)
        duration_ms = 10000
        main_period = TimePeriod(start_ms=now_ms, duration_ms=duration_ms)
        trimmed_right = main_period.trim_right(duration_ms // 2)
        self.assertTrue(trimmed_right.duration_sec * 1000 == duration_ms // 2)
        self.assertTrue(trimmed_right.start_ms == now_ms)
        overtrimmed = main_period.trim_right(duration_ms * 2)
        self.assertTrue(overtrimmed.duration_sec == 0)
        self.assertTrue(overtrimmed.start_ms == now_ms)
        with self.assertRaises(RuntimeError):
            TimePeriod(now_ms, None).trim_right(duration_ms)

    def test_is_among(self):
        now_ms = int(time.monotonic() * 1000)
        duration_ms = 10000
        main_period = TimePeriod(start_ms=now_ms, duration_ms=duration_ms)
        gap = 2000
        current_period = TimePeriod(
            start_ms=now_ms - duration_ms - gap, duration_ms=duration_ms)
        periods_list = [current_period]
        for _ in range(10):
            current_period = TimePeriod(
                start_ms=current_period.end_ms + gap, duration_ms=duration_ms)
            periods_list.append(current_period)
        self.assertTrue(main_period.is_among(periods_list))
        shifted_period = TimePeriod(
            start_ms=now_ms - duration_ms - gap * 2, duration_ms=duration_ms)
        self.assertFalse(shifted_period.is_among(periods_list))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
