# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from installation import time_server
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import WindowsAccess
from tests.merged_systems.time_synchronization.running_time import mediaserver_and_os_time_are_in_sync
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_time_sync_with_internet


def _test_follow_os_time_until_internet_on(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    first_mediaserver = two_mediaservers.first.installation()
    second_mediaserver = two_mediaservers.second.installation()
    if isinstance(first_mediaserver.os_access, WindowsAccess):
        first_mediaserver.os_access.disable_netprofm_service()
    if isinstance(second_mediaserver.os_access, WindowsAccess):
        second_mediaserver.os_access.disable_netprofm_service()
    first_mediaserver.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=1))
    second_mediaserver.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(hours=2))
    first_mediaserver.update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 2000})
    first_mediaserver.start()
    first_mediaserver.api.setup_local_system()
    second_mediaserver.start()
    second_mediaserver.api.setup_local_system()
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    assert mediaserver_and_os_time_are_in_sync(first_mediaserver.api, first_mediaserver.os_access)
    assert mediaserver_and_os_time_are_in_sync(second_mediaserver.api, second_mediaserver.os_access)
    first_mediaserver.os_access.cache_dns_in_etc_hosts([*public_ip_check_addresses, time_server])
    first_mediaserver.allow_time_server_access()
    wait_until_mediaserver_time_sync_with_internet(first_mediaserver.api, timeout_sec=180)
    wait_until_mediaserver_time_sync_with_internet(second_mediaserver.api, timeout_sec=180)
    assert first_mediaserver.api.time_sync_with_internet_is_enabled()
