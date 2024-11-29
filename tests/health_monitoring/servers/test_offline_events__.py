# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _wait_no_offline_events(mediaserver_api, *server_ids, timeout_sec=30):
    def _no_offline_events():
        servers = mediaserver_api.get_metrics('servers')
        for server_id in server_ids:
            if servers[server_id]['offline_events'] != 0:
                return False
        return True
    wait_for_truthy(_no_offline_events, timeout_sec=timeout_sec)


def _test_offline_events(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    history_age_sec = 120
    for mediaserver in first, second:
        mediaserver.update_ini('nx_utils', {'valueHistoryAgeDelimiter': 24 * 3600 / history_age_sec})
        mediaserver.api.restart()
    first_id = first.api.get_server_id()
    second_id = second.api.get_server_id()
    guard_interval_sec = 15
    _wait_no_offline_events(
        first.api, first_id, second_id, timeout_sec=history_age_sec + guard_interval_sec)
    for i in range(1, 5):
        second.stop()
        first.api.wait_for_metric('servers', second_id, 'offline_events', expected=i)
        second.start()
        time.sleep(5)
        assert first.api.get_metrics('servers', second_id, 'offline_events') == i
    _wait_no_offline_events(first.api, second_id, timeout_sec=history_age_sec + guard_interval_sec)
