# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from contextlib import contextmanager
from datetime import timedelta
from functools import partial

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_time_change(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.api.become_primary_time_server()
    server_id = mediaserver.api.get_server_id()
    # Reduce time of metric accumulation.
    history_age_sec = 10  # Age less than 10 seconds does not work for this test.
    mediaserver.update_ini('nx_utils', {'valueHistoryAgeDelimiter': 24 * 3600 / history_age_sec})
    mediaserver.api.set_system_settings({'osTimeChangeCheckPeriodMs': 1000})
    mediaserver.api.restart()
    alarm_path = ('servers', mediaserver.api.get_server_id(), 'info', 'vmsTimeChanged24h')
    delta = -timedelta(seconds=5)
    with _time_change_detected(mediaserver.api, delta):
        mediaserver.os_access.shift_time(delta)
    wait_for_time_changed = partial(
        mediaserver.api.wait_for_metric,
        'servers', server_id, 'time_changed_24h', timeout_sec=history_age_sec + 20)
    wait_for_time_changed(expected=1)
    assert alarm_path not in mediaserver.api.list_metrics_alarms()
    for _ in range(4):
        with _time_change_detected(mediaserver.api, delta):
            mediaserver.os_access.shift_time(delta)
    wait_for_time_changed(expected=5)
    assert alarm_path not in mediaserver.api.list_metrics_alarms()
    with _time_change_detected(mediaserver.api, delta):
        mediaserver.os_access.shift_time(delta)
    wait_for_time_changed(expected=6)
    alarm = Alarm(
        level='warning',
        text='time was synchronized 6 times in the last 24 hours. Check hardware.')
    assert alarm in mediaserver.api.list_metrics_alarms()[alarm_path]
    wait_for_time_changed(expected=0)
    assert alarm_path not in mediaserver.api.list_metrics_alarms()


@contextmanager
def _time_change_detected(mediaserver_api, delta, timeout_sec=30):
    tolerance = timedelta(seconds=1.5)
    start_at = time.monotonic()
    time_before = mediaserver_api.get_datetime()
    yield
    start = time.monotonic()
    while time.monotonic() - start < timeout_sec:
        elapsed = time.monotonic() - start_at
        expected_time = time_before + timedelta(seconds=elapsed)
        diff = abs(delta - (mediaserver_api.get_datetime() - expected_time))
        if diff < tolerance:
            break
        time.sleep(1)
    else:
        raise RuntimeError(f"Failed to detect time change in {timeout_sec}")
