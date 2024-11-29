# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.common import configure_two_mediaservers_stand
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync


def _test_secondary_follows_primary(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    configure_two_mediaservers_stand(two_mediaservers)
    primary = two_mediaservers.first.installation()
    secondary = two_mediaservers.second.installation()
    secondary.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=-10))
    wait_until_mediaserver_and_os_time_sync(secondary.api, primary.os_access, timeout_sec=30)
    secondary.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=-1))
    wait_until_mediaserver_and_os_time_sync(secondary.api, primary.os_access, timeout_sec=30)
    secondary.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=1))
    wait_until_mediaserver_and_os_time_sync(secondary.api, primary.os_access, timeout_sec=30)
    secondary.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=10))
    wait_until_mediaserver_and_os_time_sync(secondary.api, primary.os_access, timeout_sec=30)
