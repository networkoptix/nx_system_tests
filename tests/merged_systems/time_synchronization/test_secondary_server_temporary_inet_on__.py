# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from installation import time_server
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import WindowsAccess
from tests.merged_systems.time_synchronization.running_time import mediaserver_time_is_close_to_internet_time
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_time_sync_with_internet


def _test_secondary_server_temporary_inet_on(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    if isinstance(stand.first.os_access(), WindowsAccess):
        stand.first.os_access().disable_netprofm_service()
    if isinstance(stand.second.os_access(), WindowsAccess):
        stand.second.os_access().disable_netprofm_service()
    stand.first.os_access().shift_time(timedelta(hours=1))
    stand.second.os_access().shift_time(timedelta(hours=2))
    stand.first.installation().update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 2000})
    stand.start()
    stand.setup_system()
    stand.merge()
    wait_until_mediaserver_and_os_time_sync(stand.first.api(), stand.first.os_access(), timeout_sec=180)
    wait_until_mediaserver_and_os_time_sync(stand.second.api(), stand.second.os_access(), timeout_sec=180)
    stand.first.installation().os_access.cache_dns_in_etc_hosts([*public_ip_check_addresses, time_server])
    stand.first.installation().allow_time_server_access()
    wait_until_mediaserver_time_sync_with_internet(stand.first.api(), timeout_sec=180)
    wait_until_mediaserver_time_sync_with_internet(stand.second.api(), timeout_sec=180)
    stand.first.installation().block_time_server_access()
    stand.second.installation().stop()
    stand.first.installation().stop()
    stand.first.installation().start()
    stand.second.installation().start()
    assert mediaserver_time_is_close_to_internet_time(stand.first.api())
    assert mediaserver_time_is_close_to_internet_time(stand.second.api())
