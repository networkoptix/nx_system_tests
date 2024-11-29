# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.common import configure_two_mediaservers_stand
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync


def _test_primary_follows_vm_time(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    configure_two_mediaservers_stand(two_mediaservers)
    primary = two_mediaservers.first.installation()
    wait_until_mediaserver_and_os_time_sync(primary.api, primary.os_access, timeout_sec=30)
