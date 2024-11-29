# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_log_level(distrib_url, one_vm_type, server_log_level, is_triggered, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver_api = one_mediaserver.api()
    mediaserver.remove_logging_ini()
    mediaserver.set_main_log_level(server_log_level)
    mediaserver.stop()
    mediaserver.start()
    alarms = mediaserver_api.list_metrics_alarms()
    server_id = mediaserver_api.get_server_id()

    if is_triggered:
        expected_stop_alarm = Alarm(
            level='warning',
            text=(
                f'current Logging level is {server_log_level}. '
                'Recommended Logging level is Info.'),
            )
        assert expected_stop_alarm in alarms['servers', server_id, 'load', 'logLevel']
    else:
        assert not alarms['servers', server_id, 'load', 'logLevel']
