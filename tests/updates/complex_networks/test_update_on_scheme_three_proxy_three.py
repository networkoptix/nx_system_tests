# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import setup_system
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.updates.common import platforms
from tests.updates.complex_networks.common import perform_system_update


class test_v4plus(VMSTest):
    """Test update on scheme three proxy three.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_update_on_scheme_three_proxy_three(args.distrib_url, 'v4plus', exit_stack)


def _test_update_on_scheme_three_proxy_three(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [system, _, _] = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'a1', 'type': 'ubuntu22'},
            {'alias': 'a2', 'type': 'ubuntu22'},
            {'alias': 'a3', 'type': 'ubuntu22'},
            {'alias': 'proxy', 'type': 'ubuntu22'},
            {'alias': 'b1', 'type': 'ubuntu22'},
            {'alias': 'b2', 'type': 'ubuntu22'},
            {'alias': 'b3', 'type': 'ubuntu22'},
            ],
        'mergers': [],
        'networks': {
            '10.254.1.0/24': {'a1': None, 'a2': None, 'a3': None, 'proxy': None},
            '10.254.2.0/24': {'b1': None, 'b2': None, 'b3': None, 'proxy': None},
            },
        }))
    setup_system(system, [
        {'local': 'proxy', 'network': '10.254.1.0/24', 'remote': 'a1', 'take_remote_settings': False},
        {'local': 'proxy', 'network': '10.254.1.0/24', 'remote': 'a2', 'take_remote_settings': False},
        {'local': 'proxy', 'network': '10.254.1.0/24', 'remote': 'a3', 'take_remote_settings': False},
        {'local': 'proxy', 'network': '10.254.2.0/24', 'remote': 'b1', 'take_remote_settings': False},
        {'local': 'proxy', 'network': '10.254.2.0/24', 'remote': 'b2', 'take_remote_settings': False},
        {'local': 'proxy', 'network': '10.254.2.0/24', 'remote': 'b3', 'take_remote_settings': False},
        ])
    perform_system_update(updates_supplier, system.values(), platforms['ubuntu22'])


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v4plus()]))
