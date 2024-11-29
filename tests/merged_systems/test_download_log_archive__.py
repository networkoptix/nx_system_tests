# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LogType
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_download_log_archive(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.remove_logging_ini()
    two.remove_logging_ini()
    one.set_main_log_level('verbose')
    two.set_main_log_level('verbose')
    one.start()
    two.start()
    one.api.setup_local_system()
    two.api.setup_local_system()
    merge_systems(one, two, take_remote_settings=False)
    one.api.set_log_levels({LogType.MAIN: 'none'})
    two.api.set_log_levels({LogType.MAIN: 'none'})
    [first_log] = one.list_log_files('main.log')
    [second_log] = two.list_log_files('main.log')
    first_server_id = one.api.get_server_id()
    with two.api.main_log_extracted(first_server_id) as first_log_from_second_api:
        assert first_log_from_second_api.stat().st_size == first_log.stat().st_size
    second_server_id = two.api.get_server_id()
    with one.api.main_log_extracted(second_server_id) as second_log_from_first_api:
        assert second_log_from_first_api.stat().st_size == second_log.stat().st_size
