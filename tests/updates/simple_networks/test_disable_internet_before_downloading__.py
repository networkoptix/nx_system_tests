# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from installation import public_ip_check_addresses
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.updates.common import platforms
from tests.waiting import wait_for_truthy


def _test_disable_internet_before_downloading(distrib_url, two_vm_types, api_version, has_public_ip, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    for mediaserver in first, second:
        # This value should not be too small. Otherwise, mediaserver may have problems
        # losing its public IP address
        mediaserver.update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 2000})
        mediaserver.os_access.cache_dns_in_etc_hosts(public_ip_check_addresses)
        mediaserver.allow_public_ip_discovery()
        mediaserver.disable_update_files_verification()
        mediaserver.start()
        mediaserver.api.setup_local_system()
    merge_systems(first, second, take_remote_settings=False)
    updates_supplier = installer_supplier.update_supplier()
    vm_types = set(two_vm_types)
    update_archive = updates_supplier.fetch_server_updates([platforms[v] for v in vm_types])
    _wait_until_has_public_ip(first.api)
    _wait_until_has_public_ip(second.api)
    second.block_public_ip_discovery()
    if not has_public_ip:
        wait_for_truthy(
            lambda: not second.api.has_public_ip(),
            description="Public IP disappeared")
    update_server = UpdateServer(update_archive, first.os_access.source_address())
    exit_stack.enter_context(update_server.serving())
    first.api.prepare_update(update_server.update_info())


def _wait_until_has_public_ip(api: MediaserverApi, timeout_sec: float = 10):
    # The process of enable public IP discovery takes some time.
    end_at = time.monotonic() + timeout_sec
    while True:
        if api.has_public_ip():
            return
        elif end_at < time.monotonic():
            raise RuntimeError(f"{api} has not public IP for {timeout_sec} sec")
        time.sleep(1)
