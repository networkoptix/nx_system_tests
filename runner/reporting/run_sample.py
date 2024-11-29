# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _run_test(test_id):
    subprocess.check_call([sys.executable, *shlex.split(test_id)])


_root = Path(__file__).parent.parent.parent
assert str(_root) in sys.path

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    os.environ['PYTHONPATH'] = str(_root)
    _run_test('-m reporting.test_sample test_with_exit_stack_passes')
    _run_test('-m reporting.test_sample test_with_exit_stack_fails_in_function')
    _run_test('-m reporting.test_sample test_with_exit_stack_fails_in_exit_stack')
    _run_test('-m reporting.test_sample test_with_exit_stack_fails_in_function_and_exit_stack')
