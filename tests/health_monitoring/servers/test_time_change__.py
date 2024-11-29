# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from installation import time_server
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_time_change(distrib_url, one_vm_type, shift, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    os_access = mediaserver.os_access
    mediaserver.update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 500})
    mediaserver.start()
    api.setup_local_system()
    server_id = api.get_server_id()
    os_access.cache_dns_in_etc_hosts([time_server, *public_ip_check_addresses])
    os_access.shift_time(shift)
    mediaserver.allow_time_server_access()
    wait_for_truthy(api.has_public_ip)
    metrics = api.get_metrics('servers', server_id)
    # There can 1-2 seconds difference between VMS time and OS time with disabled internet.
    time_diff = timedelta(seconds=3)
    assert abs(metrics['vms_time'] + shift - metrics['os_time']) < time_diff
    time.sleep(5)  # Let mediaserver save time delta to database before restart
    mediaserver.block_time_server_access()
    api.restart()
    metrics = api.get_metrics('servers', server_id)
    assert abs(metrics['vms_time'] + shift - metrics['os_time']) < time_diff
