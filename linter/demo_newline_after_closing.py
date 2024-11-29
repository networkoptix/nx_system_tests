# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack

with ExitStack(
        ) as exit_stack:
    pass
pass_scalar = 123
pass_brackets = []
pass_brackets_with_post_call = [123].count(123)
pass_multiline = [
    123,
    ]
fail_multiline_with_post_call = [
    123,
    ].count(123)


def func(
        param,
        ):
    pass


def func_with_return_type(
        param,
        ) -> int:
    pass
