# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from contextlib import AbstractContextManager
from contextlib import contextmanager


def assert_raises(exc_cls: type[Exception], msg: str = None) -> AbstractContextManager[None]:
    """Asserting with the expected exception.

    >>> try:
    ...     with assert_raises(RuntimeError, 'Exception text'):
    ...         pass
    ... except Exception as exc:
    ...     assert str(exc) == 'Exception text'
    """
    return assert_raises_with_message_re(exc_cls, '', msg)


def assert_raises_with_message(
        exc_cls: type[Exception], message: str) -> AbstractContextManager[None]:
    return assert_raises_with_message_re(exc_cls, re.escape(message))


@contextmanager
def assert_raises_with_message_re(
        exc_cls: type[Exception], pattern: str, msg: str = None) -> AbstractContextManager[None]:
    try:
        yield
    except Exception as e:
        if not isinstance(e, exc_cls):
            raise
        elif re.search(pattern, str(e)) is None:
            raise Exception(msg or f"Exception {exc_cls!r} did not match {pattern!r}")
        else:
            pass
    else:
        raise Exception(msg or f"Exception {exc_cls!r} was not raised")


class Skip(Exception):
    pass


class Failure(Exception):
    pass
