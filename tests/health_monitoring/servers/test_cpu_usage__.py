# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from concurrent.futures import ThreadPoolExecutor

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import get_stream_async
from doubles.video.ffprobe import wait_for_stream
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.health_monitoring.common import configure_mediaserver_with_mjpeg_cameras

METRICS_UPDATE_INTERVAL_SEC = 2


def _collect_metrics_cpu_usage(api, server_id, duration_sec):
    collect_metrics_started_at = time.monotonic()
    vms_usage = []
    total_usage = []
    while time.monotonic() - collect_metrics_started_at < duration_sec:
        metrics_sample_timestamp = time.monotonic()
        metrics = api.get_metrics('servers', server_id)
        vms_usage.append(metrics['vms_cpu_usage'])
        total_usage.append(metrics['total_cpu_usage'])
        # CPU usage in metrics refreshes every 2 seconds.
        time.sleep(max(
            0,
            METRICS_UPDATE_INTERVAL_SEC - (time.monotonic() - metrics_sample_timestamp),
            ))
    return total_usage, vms_usage


def _standard_deviation(first_samples, second_samples):
    zipped = [*zip(first_samples, second_samples)]
    dispersion = sum((first - second)**2 for first, second in zipped) / len(zipped)
    return math.sqrt(dispersion)


def _run_mediaserver_cpu_load(api, executor, camera_ids, exit_stack, duration_sec):
    futures = []
    for url in [api.rtsp_url(camera_id) for camera_id in camera_ids]:
        futures.append(executor.submit(wait_for_stream, url))
    for future in futures:
        future.result()
    rtsp_urls = [api.rtsp_url(camera_id, codec='mpeg2video') for camera_id in camera_ids]
    for _ in range(5):
        for url in rtsp_urls:
            exit_stack.enter_context(get_stream_async(url, duration_sec=duration_sec))
    # Sleep to record mediaserver CPU usage and
    # additional 10 seconds of low CPU usage
    time.sleep(duration_sec + 10)


def _test_cpu_usage(distrib_url, one_vm_type, api_version, camera_count, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    camera_server, cameras = configure_mediaserver_with_mjpeg_cameras(
        license_server, mediaserver, camera_count)
    mediaserver_pid = mediaserver.service.status().pid
    api = mediaserver.api
    server_id = api.get_server_id()
    os_access = mediaserver.os_access
    exit_stack.enter_context(camera_server.async_serve())
    executor = exit_stack.enter_context(ThreadPoolExecutor(max_workers=20))
    duration_sec = 80
    sample_count = int(duration_sec / METRICS_UPDATE_INTERVAL_SEC)
    os_cpu_usage_fut = executor.submit(
        os_access.list_total_cpu_usage,
        METRICS_UPDATE_INTERVAL_SEC,
        sample_count,
        )
    os_process_cpu_usage_fut = executor.submit(
        os_access.list_process_cpu_usage,
        mediaserver_pid,
        METRICS_UPDATE_INTERVAL_SEC,
        sample_count,
        )
    # CPU metrics on server are cached for 2 seconds
    # and are gathered for the previous 2 seconds
    # relatively to the OS CPU counters.
    # So, wait is required for OS and API metrics to synchronise.
    time.sleep(METRICS_UPDATE_INTERVAL_SEC * 2)
    metrics_cpu_usage_fut = executor.submit(
        _collect_metrics_cpu_usage,
        api,
        server_id,
        duration_sec - METRICS_UPDATE_INTERVAL_SEC * 2,
        )
    # Sleep to record no CPU usage
    time.sleep(5)
    _run_mediaserver_cpu_load(api, executor, [c.id for c in cameras], exit_stack, 30)
    # Create peak machine CPU usage
    os_access.run_cpu_load(15)
    # Sleep for CPU to cool down and record
    # no CPU usage after that.
    time.sleep(10)
    [metrics_total_cpu_usage, metrics_process_cpu_usage] = metrics_cpu_usage_fut.result()
    os_process_cpu_sage = os_process_cpu_usage_fut.result()
    os_cpu_usage = os_cpu_usage_fut.result()
    assert _standard_deviation(metrics_total_cpu_usage, os_cpu_usage) < 0.3
    assert _standard_deviation(metrics_process_cpu_usage, os_process_cpu_sage) < 0.3
