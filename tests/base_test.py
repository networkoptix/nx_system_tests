# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
import re
from abc import ABCMeta
from typing import Sequence

from cloud_api.cloud import CloudHostArgparseAction
from directories import run_metadata
from mediaserver_scenarios.distrib_argparse_action import DistribArgparseAction
from runner.ft_test import FTTest

_logger = logging.getLogger(__name__)


class VMSTest(FTTest, metaclass=ABCMeta):

    def __init__(self):
        super().__init__()
        self._argparse_parameters.append(('--installers-url', DistribArgparseAction))


class WebAdminArgparseAction(argparse.Action):
    dest = 'webadmin_url'
    _re = re.compile(
        r'https?://\S+ | '
        r'builtin:',
        re.VERBOSE)

    def __init__(self, *, option_strings: Sequence[str], dest: str, **kwargs):
        [option, *aliases] = option_strings
        if aliases:
            raise ValueError(f"Aliases are not allowed: {aliases}")
        if not option.startswith('--'):
            raise ValueError(f"Must start with '--': {option}")
        if dest != option.lstrip('-').replace('-', '_'):
            raise ValueError(f"Custom dest is not allowed: {dest}")
        if kwargs:
            raise ValueError(f"Parameters are not allowed: {kwargs.keys()}")
        super().__init__(
            option_strings,
            self.dest,
            type=_regex_validator(self._re),
            default='builtin:',
            required=False,
            help="WebAdmin URL or 'builtin:'",
            )

    def __call__(self, parser, namespace, value, option_string=None):
        # The "dest" parameter is intentionally ignored.
        namespace.webadmin_url = value


class WebAdminTest(VMSTest, metaclass=ABCMeta):

    def __init__(self):
        super().__init__()
        self._argparse_parameters.append(('--webadmin-url', WebAdminArgparseAction))


class _CloudStateArgparseAction(argparse.Action):
    """Tells apart Cloud deployments and configurations.

    >>> _CloudStateArgparseAction._re.fullmatch('custom:foo bar')  # doctest: +ELLIPSIS
    <re.Match...
    >>> _CloudStateArgparseAction._re.fullmatch('at:2024-08-29T13:52:19.602842+00:00')  # doctest: +ELLIPSIS
    <re.Match...
    >>> _CloudStateArgparseAction._re.fullmatch('https://example.com/foo')  # doctest: +ELLIPSIS
    <re.Match...
    >>> _CloudStateArgparseAction._re.fullmatch('https://example.com/foo ')
    >>> _CloudStateArgparseAction._re.fullmatch('foo bar')
    """

    dest = 'cloud_state'
    _re = re.compile(
        r'https?://\S+ | '
        r'at:20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d.\d{6}[+-]\d\d:\d\d | '
        r'custom:.+',
        re.VERBOSE)

    def __init__(self, *, option_strings: Sequence[str], dest: str, **kwargs):
        [option, *aliases] = option_strings
        if aliases:
            raise ValueError(f"Aliases are not allowed: {aliases}")
        if not option.startswith('--'):
            raise ValueError(f"Must start with '--': {option}")
        if dest != option.lstrip('-').replace('-', '_'):
            raise ValueError(f"Custom dest is not allowed: {dest}")
        if kwargs:
            raise ValueError(f"Parameters are not allowed: {kwargs.keys()}")
        super().__init__(
            option_strings,
            self.dest,
            type=_regex_validator(self._re),
            default='at:' + run_metadata()['run_started_at_iso'],
            required=False,
            help=(
                "Control whether it's the same Cloud as before or a new one. "
                "Deployments and reconfigurations do not change cloud host. "
                "Identified only by cloud host, runs are grouped as re-runs. "
                "There is nothing similar to distrib URL of VMS for Cloud. "
                "Versions, feature flags, customization are not enough. "
                "Either assume a new state each run or let the user decide. "
                "E.g. pipeline id or deployment timestamp can be a state."),
            )

    def __call__(self, parser, namespace, value, option_string=None):
        setattr(namespace, self.dest, value)


def _regex_validator(pattern: re.Pattern):
    """Validate argument with a regex.

    >>> _regex_validator(re.compile('fo+'))('foo')
    'foo'
    >>> _regex_validator(re.compile('fo+'))('bar')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    argparse.ArgumentTypeError: ...bar...fo+...
    """

    def validator(s: str):
        if pattern.fullmatch(s):
            return s
        else:
            raise argparse.ArgumentTypeError(f"{s} does not match {pattern}")

    return validator


class CloudTest(FTTest, metaclass=ABCMeta):

    def __init__(self):
        super().__init__()
        self._argparse_parameters.append(('--test-cloud-host', CloudHostArgparseAction))
        self._argparse_parameters.append(('--cloud-state', _CloudStateArgparseAction))
