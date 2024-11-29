# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LogType
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_level_setting(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.remove_logging_ini()
    two.remove_logging_ini()
    one.set_main_log_level('none')
    two.set_main_log_level('none')
    one.start()
    two.start()
    one.api.setup_local_system()
    two.api.setup_local_system()
    merge_systems(one, two, take_remote_settings=False)
    time.sleep(5)  # To make sure the logs aren't collected after a few seconds
    assert not one.list_log_files('main.log')
    assert not two.list_log_files('main.log')
    system_log_level = 'verbose'
    one.api.set_system_log_levels({LogType.MAIN: system_log_level})
    one.api.restart()
    two.api.restart()
    first_main_log_level = one.api.list_log_levels()[LogType.MAIN]
    second_main_log_level = two.api.list_log_levels()[LogType.MAIN]
    assert one.get_main_log_level() == first_main_log_level == system_log_level
    assert two.get_main_log_level() == second_main_log_level == system_log_level
    assert one.list_log_files('main.log')
    assert two.list_log_files('main.log')
    one.api.set_log_levels({LogType.MAIN: 'none'})
    [first_log] = one.list_log_files('main.log')
    [second_log] = two.list_log_files('main.log')
    first_log_size_before = first_log.stat().st_size
    second_log_size_before = second_log.stat().st_size
    time.sleep(1)
    assert first_log_size_before == first_log.stat().st_size
    assert second_log_size_before < second_log.stat().st_size
