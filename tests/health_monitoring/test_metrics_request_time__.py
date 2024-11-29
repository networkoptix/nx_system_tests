# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from statistics import median

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_metrics_request_time(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    fake_server_count = 100
    for i in range(fake_server_count):
        primary_data = generate_mediaserver(index=i)
        one.api.add_generated_mediaserver(primary_data)
    api = one.api
    system_info = api.get_metrics('system_info')
    assert system_info['servers'] == fake_server_count + 2
    whole_system_metrics_request_time = _median_metrics_request_time(api)
    servers_metrics_request_time = _median_metrics_request_time(api, 'servers')
    server_id = api.get_server_id()
    single_server_metrics_request_time = _median_metrics_request_time(api, 'servers', server_id)
    assert whole_system_metrics_request_time / single_server_metrics_request_time > 2
    assert servers_metrics_request_time / single_server_metrics_request_time > 2


def _median_metrics_request_time(api, *metrics_path) -> float:
    times = []
    for _ in range(5):
        started_at = time.monotonic()
        api.get_filtered_raw_metric_values(*metrics_path)
        times.append(time.monotonic() - started_at)
    return median(times)
