# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_time_duration_limit_setting(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    server = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    server.remove_logging_ini()
    server.set_main_log_level('verbose')
    server.start()
    server.api.setup_local_system()
    assert server.list_log_files('main.log')
    assert not server.list_log_files('*.log.zip')
    max_duration_sec = 3  # To speed up the test
    server.api.set_max_log_file_time_duration(duration_sec=max_duration_sec)
    # Wait for at least 3 files to check rotation.
    desired_archives_amount = 3
    wait_for_truthy(
        lambda: len(server.list_log_files('*.log.zip')) >= desired_archives_amount,
        description=f"At least {desired_archives_amount} log files are rotated")
