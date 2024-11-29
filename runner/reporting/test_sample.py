# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from runner.ft_test import FTTest
from runner.ft_test import run_ft_test


class test_with_exit_stack_passes(FTTest):

    def _run(self, args, exit_stack):
        pass


class test_with_exit_stack_fails_in_function(FTTest):

    def _run(self, args, exit_stack):
        raise RuntimeError("Sample exception")


def _raise_exception(message):
    raise RuntimeError(message)


class test_with_exit_stack_fails_in_exit_stack(FTTest):

    def _run(self, args, exit_stack):
        exit_stack.callback(lambda: _raise_exception("Exception in exit stack"))


class test_with_exit_stack_fails_in_function_and_exit_stack(FTTest):

    def _run(self, args, exit_stack):
        exit_stack.callback(lambda: _raise_exception("Exception in exit stack"))
        _raise_exception("Exception in function")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_with_exit_stack_passes(),
        test_with_exit_stack_fails_in_function(),
        test_with_exit_stack_fails_in_exit_stack(),
        test_with_exit_stack_fails_in_function_and_exit_stack(),
        ]))
