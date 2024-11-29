# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import TwoMediaserverStand
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import WindowsAccess

_logger = logging.getLogger(__name__)

CHECK_INTERVAL_SEC = 1
TRAFFIC_DURATION = 75
ACCEPTABLE_DEVIATION = 65  # kbit/s


def _get_metrics_rates(mediaserver_api, interface_name, traffic_direction):
    assert traffic_direction in ('in', 'out')
    server_id = mediaserver_api.get_server_id()
    rate_name = f'{traffic_direction}_kbit'
    metrics_rates = []
    # Metrics for 1 minute are calculated based on mean values for 5 seconds.
    # So there is ~5 seconds delay between real traffic and metrics shows that traffic, which we
    # need to detect and take account for later.
    start = time.monotonic()
    while True:
        command_start = time.monotonic()
        data = mediaserver_api.get_metrics('network_interfaces', (server_id, interface_name))
        metrics_rates.append(data['rates'][rate_name])
        if time.monotonic() - start > TRAFFIC_DURATION + 75:
            break  # Don't sleep on last iteration
        sleep_sec = CHECK_INTERVAL_SEC - (time.monotonic() - command_start)
        time.sleep(sleep_sec if sleep_sec > 0 else 0)
    return metrics_rates


def _get_metrics_rates_in(mediaserver_api, interface_name):
    return _get_metrics_rates(mediaserver_api, interface_name, 'in')


def _get_metrics_rates_out(mediaserver_api, interface_name):
    return _get_metrics_rates(mediaserver_api, interface_name, 'out')


def _get_os_stats(os_networking, nic_id, duration_sec, traffic_direction):
    assert traffic_direction in ('in', 'out')
    stats = []
    start = time.monotonic()
    while True:
        command_start = time.monotonic()
        rx_bytes, tx_bytes = os_networking.get_interface_stats(nic_id)
        stats.append(rx_bytes if traffic_direction == 'in' else tx_bytes)
        if time.monotonic() - start > duration_sec:
            break
        sleep_sec = CHECK_INTERVAL_SEC - (time.monotonic() - command_start)
        time.sleep(sleep_sec if sleep_sec > 0 else 0)
    return stats


def _get_os_stats_in(os_networking, nic_id, duration_sec):
    return _get_os_stats(os_networking, nic_id, duration_sec, 'in')


def _get_os_stats_out(os_networking, nic_id, duration_sec):
    return _get_os_stats(os_networking, nic_id, duration_sec, 'out')


def _calculate_os_rates(os_stats):
    samples_per_minute = 60 // CHECK_INTERVAL_SEC
    result = []
    for current_bytes, previous_bytes in zip(os_stats[samples_per_minute:], os_stats):
        result.append((current_bytes - previous_bytes) * 8 / 1000 / 60)
    return result


def _compare_metrics_and_os_rates(metrics_rates, os_rates, label):
    _logger.info("Computing least squares for %s", label)
    squares = [
        sum((os - metrics)**2 for os, metrics in zip(os_rates, metrics_rates[delay:]))
        for delay in range(0, 20)]
    _logger.info("Squares: %s", squares)
    standard_deviation = math.sqrt(min(squares) / len(os_rates))
    _logger.info("Standard deviation: %s", standard_deviation)
    return standard_deviation < ACCEPTABLE_DEVIATION


def prepare_two_mediaservers_with_cameras(
        license_server: LocalLicenseServer,
        two_mediaservers: TwoMediaserverStand,
        ):
    camera_server = MultiPartJpegCameraServer()
    two_mediaservers.start()
    two_mediaservers.setup_system()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    first_ip = two_mediaservers.first.subnet_ip()
    _logger.info("Preparing servers")
    with license_server.serving():
        first.allow_license_server_access(license_server.url())
        first.api.set_license_server(license_server.url())
        brand = first.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
        first.api.activate_license(key)
        second.allow_license_server_access(license_server.url())
        second.api.set_license_server(license_server.url())
        brand = second.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
        second.api.activate_license(key)
    [first_camera] = add_cameras(first, camera_server)
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Serve 30 seconds for cameras discovery.
        serve = executor.submit(camera_server.serve, time_limit_sec=30)
        _logger.info("Serving started")
        external_stream_url = first.api.rtsp_url(first_camera.id)
        parsed = urlparse(external_stream_url)
        stream_url = parsed._replace(netloc=f"{first_ip}:{first.port}").geturl()
        credentials = first.api.get_credentials()
        [second_camera] = second.api.add_manual_camera_sync(
            stream_url, credentials.username, credentials.password)
        serve.result()
    _logger.info("Servers prepared, proceed")
    return first_camera, second_camera


def _test_network_rates(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    license_server = LocalLicenseServer()
    [_, second_camera] = prepare_two_mediaservers_with_cameras(license_server, two_mediaservers)
    camera_id = second_camera.id
    first_nic_id = two_mediaservers.first.subnet_nic()
    second_nic_id = two_mediaservers.second.subnet_nic()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    if isinstance(first.os_access, WindowsAccess):
        first.os_access.disable_netprofm_service()
    if isinstance(second.os_access, WindowsAccess):
        second.os_access.disable_netprofm_service()
    first_iface_name = first.os_access.networking.get_interface_name(first_nic_id)
    second_iface_name = second.os_access.networking.get_interface_name(second_nic_id)
    first_networking = first.os_access.networking
    second_networking = second.os_access.networking
    if isinstance(first.os_access, WindowsAccess):
        # The first run in Windows may take a long time, which can lead to fewer stats than needed.
        first_networking.get_interface_stats(first_nic_id)
    if isinstance(second.os_access, WindowsAccess):
        # The first run in Windows may take a long time, which can lead to fewer stats than needed.
        second_networking.get_interface_stats(second_nic_id)
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as executor:
        serve = executor.submit(camera_server.serve, time_limit_sec=TRAFFIC_DURATION + 60)
        first_os_stats_fut = executor.submit(
            _get_os_stats_out, first_networking, first_nic_id, TRAFFIC_DURATION + 120)
        second_os_stats_fut = executor.submit(
            _get_os_stats_in, second_networking, second_nic_id, TRAFFIC_DURATION + 120)
        _logger.info("Collect stats for 60 seconds with no traffic")
        time.sleep(60)
        _logger.info("Got OS stats before recording, seconds passed %s", time.monotonic() - start)
        second.api.start_recording(camera_id)
        first_metrics_fut = executor.submit(_get_metrics_rates_out, first.api, first_iface_name)
        second_metrics_fut = executor.submit(_get_metrics_rates_in, second.api, second_iface_name)
        _logger.info(
            "Sleeping %s seconds, seconds passed %s", TRAFFIC_DURATION, time.monotonic() - start)
        time.sleep(TRAFFIC_DURATION)
        _logger.info("Stop recording, seconds passed %s", time.monotonic() - start)
        second.api.stop_recording(camera_id)
        _logger.info("Wait for serving to stop")
        serve.result()
        first_metrics_rates = first_metrics_fut.result()
        second_metrics_rates = second_metrics_fut.result()
        first_os_stats = first_os_stats_fut.result()
        second_os_stats = second_os_stats_fut.result()
    _logger.info("Got results, seconds passed %s", time.monotonic() - start)
    first_os_rates = _calculate_os_rates(first_os_stats)
    assert first_os_rates, f"Failed to calculate OS rates for the {two_vm_types[0]} server."
    second_os_rates = _calculate_os_rates(second_os_stats)
    assert second_os_rates, f"Failed to calculate OS rates for the {two_vm_types[1]} server."
    _logger.info("First server's metrics rates:\n%s", first_metrics_rates)
    _logger.info("First server's os rates:\n%s", first_os_rates)
    _logger.info("Second server's metrics rates:\n%s", second_metrics_rates)
    _logger.info("Second server's os rates:\n%s", second_os_rates)
    first_within_tolerance = _compare_metrics_and_os_rates(
        first_metrics_rates, first_os_rates, 'first')
    second_within_tolerance = _compare_metrics_and_os_rates(
        second_metrics_rates, second_os_rates, 'second')
    assert first_within_tolerance and second_within_tolerance
