# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync


def _test_system_follows_primary_os_time(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    first_mediaserver = two_mediaservers.first.installation()
    second_mediaserver = two_mediaservers.second.installation()
    for server in (first_mediaserver, second_mediaserver):
        server.os_access.set_datetime(datetime.now(timezone.utc))
    first_mediaserver.api.become_primary_time_server()
    first_mediaserver.os_access.shift_time(timedelta(hours=5))
    wait_until_mediaserver_and_os_time_sync(first_mediaserver.api, first_mediaserver.os_access, timeout_sec=30)
    wait_until_mediaserver_and_os_time_sync(second_mediaserver.api, first_mediaserver.os_access, timeout_sec=30)
    second_mediaserver.api.become_primary_time_server()
    wait_until_mediaserver_and_os_time_sync(first_mediaserver.api, second_mediaserver.os_access, timeout_sec=30)
    wait_until_mediaserver_and_os_time_sync(second_mediaserver.api, second_mediaserver.os_access, timeout_sec=30)
