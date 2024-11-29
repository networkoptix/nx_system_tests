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
    """Test update on scheme two with internet.

    Selection-Tag: gitlab
    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_update_on_scheme_two_with_internet(args.distrib_url, 'v4plus', exit_stack)


def _test_update_on_scheme_two_with_internet(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [system, _, _] = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            ],
        'mergers': [],
        'networks': {
            '10.254.1.0/24': {'first': None, 'second': None},
            },
        }))
    setup_system(system, [
        {'local': 'first', 'network': '10.254.1.0/24', 'remote': 'second', 'take_remote_settings': True},
        ])
    perform_system_update(updates_supplier, system.values(), platforms['ubuntu22'])


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v4plus()]))
