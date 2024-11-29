# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import logging
import os
import socket
from argparse import ArgumentParser
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from traceback import format_exception
from typing import Any
from typing import Callable
from typing import Sequence

from _internal.service_registry import elasticsearch
from config import global_config
from directories import get_run_dir
from directories import run_metadata
from installation import ErrorLogsFound
from long_tests._common import get_installers_url
from runner.reporting.pretty_traceback import dump_traceback


def run_test(test_func: '_ComparisonTestFunctionWrapper') -> int:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('installation._vms_benchmark').setLevel(logging.WARNING)
    standard_formatter = logging.Formatter(
        '%(asctime)s '
        '%(threadName)10s '
        '%(name)s '
        '%(levelname)s '
        '%(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(standard_formatter)
    stream_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(stream_handler)
    run_dir = get_run_dir()
    file_handler = logging.FileHandler(run_dir / 'debug.log', encoding='utf8')
    file_handler.setFormatter(standard_formatter)
    logging.getLogger().addHandler(file_handler)
    message = {
        'type': test_func.test_name,
        'started_at': datetime.utcnow().isoformat(timespec='microseconds'),
        'installers_url': get_installers_url(),
        'run_ft_revision': run_metadata()['run_ft_revision'],
        'run_hostname': run_metadata()['run_hostname'],
        'artifacts_url': _get_artifacts_url(run_dir),
        }
    result = None
    try:
        try:
            with ExitStack() as exit_stack:
                result = test_func(exit_stack=exit_stack)
        except ErrorLogsFound:
            # result is not None if ErrorLogsFound is raised in callback functions
            # (Mediaserver.check_for_error_logs(), in this case).
            if result is None:
                raise
            _logger.exception(
                "Error logs were found during the teardown process, but that's not the focus of "
                "this test. It's acceptable as long as the test completed without any other errors")
        message.update(result)
    except Exception as exc:
        dump_traceback(exc, run_dir)
        message['error'] = ''.join(format_exception(exc)).rstrip()
        message['task_status'] = 'Fail'
        _logger.exception("Test %s failed", test_func.test_name)
        return 200
    else:
        message['task_status'] = 'Success'
        return 0
    finally:
        message['finished_at'] = datetime.utcnow().isoformat(timespec='microseconds')
        _logger.info('Send message to Elasticsearch: %s', message)
        elasticsearch.send_flush('ft-measure-{YYYY}', message)


def _get_artifacts_url(run_dir: Path) -> str:
    if 'http_share' in global_config:
        _, url = global_config['http_share'].split(os.pathsep, 1)
        url = url.format(
            home=Path.home(),
            username=getpass.getuser(),
            hostname=socket.gethostname(),
            )
        relative_path = run_dir.absolute().relative_to(Path.home())
        return url.rstrip("/") + '/' + str(relative_path)
    else:
        return str(run_dir.absolute())


def select_comparison_test(
        args: Sequence[str],
        test_functions: Sequence['_ComparisonTestFunctionWrapper'],
        ) -> '_ComparisonTestFunctionWrapper':
    parser = ArgumentParser()
    function_names = [n.func_name() for n in test_functions]
    parser.add_argument(
        '--test-function',
        required=True,
        choices=function_names,
        )
    parsed_args, _ = parser.parse_known_args(args)
    for function in test_functions:
        if function.func_name() == parsed_args.test_function:
            return function
    else:
        raise RuntimeError(f"Failed to find test function {parsed_args.test_function!r}")


class ComparisonTest:

    def __init__(self, test_name: str):
        self._test_name = test_name

    def __call__(self, func: Callable) -> '_ComparisonTestFunctionWrapper':
        return _ComparisonTestFunctionWrapper(func, self._test_name)


class _ComparisonTestFunctionWrapper:

    def __init__(self, func: Callable, test_name: str):
        self.test_name = test_name
        self._func = func

    def __call__(self, *args, **kwargs) -> Any:
        return self._func(*args, **kwargs)

    def func_name(self) -> str:
        return self._func.__name__


_logger = logging.getLogger(__name__)
