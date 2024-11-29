# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Mediaserver .ini files.

See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/83895081.

>>> from directories import get_run_dir
>>> artifacts_dir = get_run_dir()
>>> path = artifacts_dir / 'dummy.ini'
>>> read_ini(path)
{}
>>> update_ini(path, {'a': '1'})
>>> read_ini(path)
{'a': '1'}
>>> update_ini(path, {'b': '2'})
>>> read_ini(path)
{'a': '1', 'b': '2'}
"""

import logging
from typing import Any
from typing import Mapping

_logger = logging.getLogger(__name__)


def read_ini(path):
    try:
        text = path.read_text()
    except FileNotFoundError:
        _logger.info("%s: doesn't exist", path)
        return {}
    else:
        _logger.info("%s: old:\n%s", path, text)
        # Config here is parsed by hand, because Mediaserver's .ini doesn't
        # support sections, which are always created by ConfigParser.
        result = {}
        for line in text.splitlines():
            key, value = line.split('=')
            result[key] = value
        return result


def _write_ini(path, all_values):
    lines = [f'{key}={value}' for key, value in all_values.items()]
    text = '\n'.join(lines)
    _logger.info("%s: new:\n%s", path, text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def update_ini(path, new_values: Mapping[str, Any]):
    old_values = read_ini(path)
    _write_ini(path, {**old_values, **new_values})
