# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from uuid import UUID

from directories import get_run_dir
from doubles.statserver.statserver_dummy import StatisticsServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_statistics_parameters(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    dummy_statserver = exit_stack.enter_context(StatisticsServer(('0.0.0.0', 0)))
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    os_access = one_mediaserver.mediaserver().os_access
    dummy_statserver_address = os_access.source_address()
    api = one_mediaserver.mediaserver().api
    small_time_cycle_sec = 40
    large_time_cycle_sec = small_time_cycle_sec * 2
    api.disable_statistics()
    [_, dummy_statserver_port] = dummy_statserver.socket.getsockname()
    api.add_statistics_server(f'http://{dummy_statserver_address}:{dummy_statserver_port}')
    # Actual time cycle is random 30%-80% of specified cycle.
    # See VMS-19662.
    api.set_statistics_time_cycle(small_time_cycle_sec)
    dummy_statserver.ensure_no_requests_received(small_time_cycle_sec * 1.2)
    # Mediaserver's statistics worker sleeps for 10 seconds between actions. Need to account that.
    mediaserver_sleep_sec = 10
    api.enable_statistics()
    # Wait until enabled statistics is detected by mediaserver.
    time.sleep(mediaserver_sleep_sec)
    system_guid = api.get_local_system_id()
    for time_cycle in (small_time_cycle_sec, large_time_cycle_sec):
        # To make the load on the statserver uniform, the mediaserver chooses the statistics
        # reporting period randomly between 0.3*cycle and 0.8*cycle.
        # The worker checks if it's time to report every 10 seconds.
        max_report_period_sec = _ceil(time_cycle * 0.8, mediaserver_sleep_sec)
        api.set_statistics_time_cycle(time_cycle)
        time.sleep(mediaserver_sleep_sec)
        # Mediaserver calculates and stores the planned report time, and then periodically
        # checks if that time has come. This planned time is calculated using
        # the statisticsReportTimeCycle value. But changing this value does not affect
        # the current planned time, only the next one. Thus, it is necessary to wait for
        # the arrival of the report planned with the previous statisticsReportTimeCycle value,
        # and only then with the new one.
        dummy_statserver.handle_request_with_timeout(max_report_period_sec + 3)
        for _ in range(3):
            started = time.monotonic()
            # Wait 3 additional seconds in case report is sent right after max_report_period_sec
            request = dummy_statserver.handle_request_with_timeout(max_report_period_sec + 3)
            finished = time.monotonic()
            assert finished - started >= time_cycle * 0.3
            assert request.method == 'POST'
            assert request.path == '/statserver/api/report'
            assert UUID(request.content['systemId']) == system_guid


def _ceil(value, factor):
    return math.ceil(value / factor) * factor
