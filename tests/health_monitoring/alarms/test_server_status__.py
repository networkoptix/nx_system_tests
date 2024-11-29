# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _offline_alarm_cleared(api, server_id):
    return not api.list_metrics_alarms()['servers', server_id, 'availability', 'status']


def _test_server_status(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()

    for stopped, running in ((first, second), (second, first)):
        stopped_id = stopped.api.get_server_id()
        running_id = running.api.get_server_id()
        stopped.stop()
        alarms = running.api.list_metrics_alarms()
        expected_stop_alarm = Alarm(level='error', text='is offline')
        assert expected_stop_alarm in alarms['servers', stopped_id, 'availability', 'status']
        assert not alarms['servers', running_id, 'availability', 'status']
        stopped.start()
        wait_for_truthy(_offline_alarm_cleared, args=(running.api, stopped_id), timeout_sec=10)
