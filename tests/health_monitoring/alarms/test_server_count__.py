# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_server_count(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver_api = one_mediaserver.mediaserver().api
    local_system_id = mediaserver_api.get_local_system_id()
    alarm_path = ('systems', local_system_id, 'info', 'servers')

    for i in range(2, 100):
        mediaserver_api.add_dummy_mediaserver(i)

    assert mediaserver_api.get_metrics('system_info', 'servers') == 99
    assert not mediaserver_api.list_metrics_alarms()[alarm_path]

    expected_alarm = Alarm(
        level='warning',
        text=(
            'The maximum number of 100 servers per system is reached. '
            'Create another system to use more servers.'))
    # 100 servers alarms
    mediaserver_api.add_dummy_mediaserver(100)
    assert mediaserver_api.get_metrics('system_info', 'servers') == 100
    assert expected_alarm in mediaserver_api.list_metrics_alarms()[alarm_path]
    # 101 servers alarms
    mediaserver_api.add_dummy_mediaserver(101)
    assert mediaserver_api.get_metrics('system_info', 'servers') == 101
    assert expected_alarm in mediaserver_api.list_metrics_alarms()[alarm_path]
