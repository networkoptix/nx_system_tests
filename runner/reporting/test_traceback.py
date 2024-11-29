# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import tempfile
import unittest
from pathlib import Path

from runner.reporting.pretty_traceback import TracebackDump
from runner.reporting.pretty_traceback import TracebackToHTML
from runner.reporting.pretty_traceback import TracebackToText


class TestTraceback(unittest.TestCase):

    def test_traceback(self):
        try:
            func_level1()
            self.fail('Test must raise an exception')
        except Exception as exc_level3:
            try:
                raise IndexError('Exception level 2') from exc_level3
            except IndexError:
                try:
                    raise LookupError('Exception level 1')
                except LookupError as exc_level1:
                    log_file = Path(tempfile.gettempdir()) / 'traceback.log'
                    log_file.unlink(True)
                    tb = TracebackDump(exc_level1)
                    tb.save(TracebackToText(log_file))
                    data = log_file.read_text()
                    self.assertGreater(len(data), 99)
                    _logger.info("Traceback file in plain text format: %s", log_file)
                    html_file = Path(tempfile.gettempdir()) / 'traceback.html'
                    html_file.unlink(True)
                    tb.save(TracebackToHTML(html_file))
                    data = html_file.read_text()
                    self.assertGreater(len(data), 99)
                    _logger.info("Traceback file in html format: %s", html_file)


def func_level1():
    local_var_level1 = 3.14
    func_level2(local_var_level1)


def func_level2(param: float):
    local_var_level2 = 99 + param
    func_raise_exception(str(local_var_level2))


def func_raise_exception(param: str):
    local_var_level3 = f'test value {param}'
    very_long_variable = 'Bum! ' * 999 + local_var_level3
    raise RuntimeError(f'It is not an error! \n{very_long_variable}')


_logger = logging.getLogger(__name__)
