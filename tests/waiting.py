# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import functools
import logging
import time
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Optional

_logger = logging.getLogger(__name__)


class Wait:

    def __init__(
            self,
            until: Optional[str],
            timeout_sec: float = 30,
            max_delay_sec: float = 5,
            ):
        self._until = until
        assert timeout_sec is not None
        self._timeout_sec = timeout_sec
        self._max_delay_sec = max_delay_sec
        self._started_at = time.monotonic()
        self._last_checked_at = self._started_at
        self._attempts_made = 0
        self.delay_sec = max_delay_sec / 16.
        _logger.debug(
            "Waiting until %s: %.1f sec.",
            self._until, self._timeout_sec)

    def again(self):
        now = time.monotonic()
        since_start_sec = time.monotonic() - self._started_at
        if since_start_sec > self._timeout_sec:
            _logger.warning(
                "Timed out waiting until %s: %g/%g sec, %d attempts.",
                self._until, since_start_sec, self._timeout_sec, self._attempts_made)
            return False
        since_last_checked_sec = now - self._last_checked_at
        if since_last_checked_sec < self.delay_sec:
            _logger.debug(
                "Continue waiting (asked earlier) until %s: %.1f/%.1f sec, %d attempts, delay %.1f sec.",
                self._until, since_start_sec, self._timeout_sec, self._attempts_made, self.delay_sec)
            return True
        self._attempts_made += 1
        self.delay_sec = min(self._max_delay_sec, self.delay_sec * 2)
        _logger.debug(
            "Continue waiting until %s: %.1f/%.1f sec, %d attempts, delay %.1f sec.",
            self._until, since_start_sec, self._timeout_sec, self._attempts_made, self.delay_sec)
        self._last_checked_at = now
        return True

    def sleep(self):
        _logger.debug("Sleep for %.1f seconds" % self.delay_sec)
        time.sleep(self.delay_sec)


def _make_call_description(func, *args):
    func_str = _description_from_func(func)
    args_str = ', '.join(['{!r}'.format(arg) for arg in args])
    return '{}({})'.format(func_str, args_str)


class WaitTimeout(Exception):

    def __init__(self, timeout_sec, message):
        super(WaitTimeout, self).__init__(message)
        self.timeout_sec = timeout_sec


def wait_for_truthy(
        get_value: Callable,
        *,
        args: Iterable = (),
        description: Optional[str] = None,
        timeout_sec: float = 30,
        ):
    if description is None:
        description = _make_call_description(get_value, *args)
    wait = Wait(description, timeout_sec)
    while True:
        result = get_value(*args)
        if result:
            _logger.debug("Waiting until %s: succeeded (got %r)", description, result)
            return result
        if not wait.again():
            raise WaitTimeout(
                timeout_sec,
                "Timed out ({} seconds) waiting for: {}".format(timeout_sec, description),
                )
        wait.sleep()


def wait_for_equal(
        get_actual: Callable,
        expected: Any,
        *,
        args: Iterable = (),
        actual_desc: Optional[str] = None,
        expected_desc: Optional[str] = None,
        timeout_sec: float = 30,
        ):
    if actual_desc is None:
        actual_desc = _make_call_description(get_actual, *args)
    if expected_desc is None:
        expected_desc = repr(expected)
    desc = "{} returns {}".format(actual_desc, expected_desc)
    wait_for_truthy(
        lambda: get_actual(*args) == expected,
        description=desc, timeout_sec=timeout_sec)


def _description_from_func(func) -> str:
    try:
        object_bound_to = func.__self__
    except AttributeError:
        if type(func) is functools.partial:
            func = func.func
        if func.__name__ == '<lambda>':
            raise ValueError("Cannot make description from lambda")
        return func.__name__
    if object_bound_to is None:
        raise ValueError("Cannot make description from unbound method")
    return '{func.__self__!r}.{func.__name__!s}'.format(func=func)
