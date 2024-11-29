# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from functools import partial

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import ApproxAbs
from mediaserver_api import ApproxRel
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _get_metrics_ram_usage(api, server_id):
    data = api.get_metrics('servers', server_id)
    return {
        'vms': data['vms_ram_usage'],
        'system': data['total_ram_usage'],
        'vms_bytes': data['vms_ram_usage_bytes'],
        'system_bytes': data['total_ram_usage_bytes']}


def _get_os_ram_usage(os_access, mediaserver_pid):
    ram_usage = os_access.get_ram_usage(mediaserver_pid)
    return {
        'vms': ApproxAbs(ram_usage.process_usage, 0.05),
        'system': ApproxAbs(ram_usage.total_usage, 0.05),
        'vms_bytes': ApproxRel(ram_usage.process_usage_bytes, 0.05),
        'system_bytes': ApproxRel(ram_usage.total_usage_bytes, 0.05)}


def _wait_metrics_equal_os(get_metrics, get_os, timeout_sec=30):
    started = time.monotonic()
    while time.monotonic() - started < timeout_sec:
        metrics = get_metrics()
        os = get_os()
        if metrics == os:
            break
    else:
        raise RuntimeError(
            "Metrics values are not equal os values: last result:\n"
            f"Metrics:\n{metrics}\nOS:\n{os}")


def _test_ram_usage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    os_access = mediaserver.os_access
    server_id = api.get_server_id()
    mediaserver_pid = mediaserver.service.status().pid
    get_metrics_ram_usage = partial(_get_metrics_ram_usage, api, server_id)
    get_os_ram_usage = partial(_get_os_ram_usage, os_access, mediaserver_pid)
    _wait_metrics_equal_os(get_metrics_ram_usage, get_os_ram_usage)
    # Large number of cameras on server will consume RAM.
    cameras = api.add_test_cameras(0, 1500)
    _wait_metrics_equal_os(get_metrics_ram_usage, get_os_ram_usage)
    for camera_id in [c.id for c in cameras]:
        api.remove_resource(camera_id)
    # Restart mediaserver to free RAM used by cameras
    api.restart()
    mediaserver_pid = mediaserver.service.status().pid
    get_os_ram_usage = partial(_get_os_ram_usage, os_access, mediaserver_pid)
    _wait_metrics_equal_os(get_metrics_ram_usage, get_os_ram_usage)
    os_access.start_ram_load()
    _wait_metrics_equal_os(get_metrics_ram_usage, get_os_ram_usage)
    os_access.stop_ram_load()
