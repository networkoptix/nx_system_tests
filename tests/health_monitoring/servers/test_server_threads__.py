# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from functools import partial

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.health_monitoring.common import configure_mediaserver_with_mjpeg_cameras


def _test_server_threads(distrib_url, one_vm_type, api_version, camera_count, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    [camera_server, cameras] = configure_mediaserver_with_mjpeg_cameras(
        license_server, mediaserver, camera_count)
    http_thread = 1  # Server opens extra thread to process HTTP request
    server_id = mediaserver.api.get_server_id()
    mediaserver_pid = mediaserver.service.status().pid
    time.sleep(5)  # Let mediaserver stabilize it's threads
    exit_stack.enter_context(camera_server.async_serve())
    get_threads = partial(mediaserver.api.get_metrics, 'servers', server_id, 'threads')
    os_before = mediaserver.os_access.get_process_thread_count(mediaserver_pid)
    metrics_before = get_threads() - http_thread
    mediaserver.api.start_recording(*[camera.id for camera in cameras])
    time.sleep(5)  # Wait so metrics are in sync with OS counters
    os_after = mediaserver.os_access.get_process_thread_count(mediaserver_pid)
    metrics_after = get_threads() - http_thread
    os_new = os_after - os_before
    if os_new <= 0:
        raise RuntimeError(
            "Server did not create new threads on cameras recording, "
            "test should come up with another mechanism on forcing server to create threads")
    metrics_new = metrics_after - metrics_before
    assert math.isclose(metrics_new, os_new, abs_tol=2)
    assert os_new < camera_count * 2 + 10
