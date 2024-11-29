# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def configure_server_with_test_cameras(mediaserver: Mediaserver):
    # Adding 10000 cameras to one server require ~ 5GB RAM. Problem solved with creating fake
    # server and adding most of cameras to it.
    mediaserver.start()
    mediaserver.api.setup_local_system()
    fake_server_id = mediaserver.api.add_dummy_mediaserver(1)
    mediaserver.api.add_test_cameras(0, 99)
    bulk = 990
    offset = 99

    for _ in range(10):
        mediaserver.api.add_test_cameras(offset, bulk, parent_id=fake_server_id)
        offset += bulk

    return mediaserver


def _test_camera_count(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    configure_server_with_test_cameras(one_mediaserver.mediaserver())
    mediaserver_api = one_mediaserver.api()
    local_system_id = mediaserver_api.get_local_system_id()
    alarm_path = ('systems', local_system_id, 'info', 'cameras')
    assert mediaserver_api.get_metrics('system_info', 'cameras') == 9999
    assert not mediaserver_api.list_metrics_alarms()[alarm_path]
    mediaserver_api.add_test_cameras(offset=9999, count=1)
    expected_alarm = Alarm(
        level='warning',
        text=(
            'The maximum number of 10000 camera channels per system is reached. '
            'Create another system to use more cameras.'))
    assert mediaserver_api.get_metrics('system_info', 'cameras') == 10000
    assert expected_alarm in mediaserver_api.list_metrics_alarms()[alarm_path]
    mediaserver_api.add_test_cameras(offset=10000, count=10)
    assert mediaserver_api.get_metrics('system_info', 'cameras') == 10010
    assert expected_alarm in mediaserver_api.list_metrics_alarms()[alarm_path]
