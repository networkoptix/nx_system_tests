# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync


def _test_uptime_is_monotonic(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    timeless_server = one_mediaserver.mediaserver()
    timeless_server.api.become_primary_time_server()
    assert timeless_server.api.is_primary_time_server()
    timeless_server.os_access.set_datetime(datetime.now(timezone.utc))
    first_uptime_sec = timeless_server.api.get_server_uptime_sec()
    timeless_server.os_access.set_datetime(datetime.now(timezone.utc) - timedelta(minutes=1))
    wait_until_mediaserver_and_os_time_sync(timeless_server.api, timeless_server.os_access, timeout_sec=30)
    second_uptime_sec = timeless_server.api.get_server_uptime_sec()
    assert float(first_uptime_sec) < float(second_uptime_sec)
