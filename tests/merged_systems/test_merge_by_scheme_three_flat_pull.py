# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import setup_system
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest


class test_v0(VMSTest):

    def _run(self, args, exit_stack):
        _test_merge_by_scheme_three_flat_pull(args.distrib_url, 'v0', exit_stack)


def _test_merge_by_scheme_three_flat_pull(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [mediaservers, _, _] = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'proxy-1', 'type': 'ubuntu22'},
            ],
        'networks': {
            '10.254.1.0/24': {'first': None, 'proxy-1': None, 'second': None},
            },
        'mergers': [],
        }))
    setup_system(mediaservers, [
        {'local': 'proxy-1', 'remote': 'first', 'take_remote_settings': True},
        {'local': 'second', 'remote': 'first', 'take_remote_settings': False},
        ])


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
