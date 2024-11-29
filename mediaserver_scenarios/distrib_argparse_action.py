# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
from typing import Sequence

from _internal.service_registry import vms_build_registry
from config import global_config


class DistribArgparseAction(argparse.Action):
    dest = 'distrib_url'

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
            default=global_config.get('installers_url') or None,
            required=not global_config.get('installers_url'),
            help="Distrib URL, 'branch:' followed by name or 'config:' followed by a config key",
            type=self._distrib_url,
            )

    @staticmethod
    def _distrib_url(value: str):
        if value.startswith(('http://', 'https://')):
            return value.rstrip('/') + '/'
        elif value.startswith('branch:'):
            branch = value.removeprefix('branch:')
            build = vms_build_registry.get_stable_build(branch)
            return build.distrib_url()
        elif value.startswith('config:'):
            return global_config[value.removeprefix('config:')]
        else:
            raise argparse.ArgumentTypeError("branch:, config: or https:// or http://")

    def __call__(self, parser, namespace, value, option_string=None):
        # The "dest" parameter is intentionally ignored.
        namespace.distrib_url = value
