# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from directories._rate_limit import NotALeader
from directories._rate_limit import TimestampFileRateLimit


class RateLimitTest(unittest.TestCase):

    def setUp(self):
        self._root = TemporaryDirectory()
        self._timestamp_file = Path(self._root.name, f'timestamp_{os.getpid()}.txt')
        self._run_period_sec = 3600

    def tearDown(self):
        self._root.cleanup()

    def test_rate_limit_common_run(self):
        self._timestamp_file.write_text(str(time.time() - self._run_period_sec * 2))
        self._test_rate_limit()

    def test_rate_limit_first_run(self):
        self._timestamp_file.unlink(missing_ok=True)
        self._test_rate_limit()

    def test_rate_limit_invalid_timestamp(self):
        self._timestamp_file.write_text('invalid_timestamp')
        self._test_rate_limit()
        content = self._timestamp_file.read_text()
        self.assertLess(abs(time.time() - float(content)), 10)

    def _test_rate_limit(self):
        burst_process_count = 20
        with ThreadPoolExecutor(max_workers=burst_process_count) as executor:
            futures = []
            for _ in range(burst_process_count):
                futures.append(executor.submit(
                    TimestampFileRateLimit(self._timestamp_file).become_leader))
            results = []
            for future in futures:
                try:
                    last_run_at = future.result()
                except NotALeader:
                    continue
                else:
                    results.append(last_run_at)
        self.assertEqual(len(results), 1, f"{len(results)} processes became leaders")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
