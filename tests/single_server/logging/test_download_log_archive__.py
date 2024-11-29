# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LogType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_download_log_archive(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    server = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    server.remove_logging_ini()
    server.set_main_log_level('verbose')
    server.start()
    server.api.setup_local_system()
    max_duration_sec = 20
    server.api.set_max_log_file_time_duration(duration_sec=max_duration_sec)
    wait_for_truthy(
        lambda: server.list_log_files('*.log.zip'),
        description="Log files are archived",
        timeout_sec=max_duration_sec)
    server.api.set_log_levels({
        LogType.MAIN: 'none',
        LogType.HTTP: 'none',
        LogType.SYSTEM: 'none',
        })
    [main_log_file] = server.list_log_files('main.log')
    main_log_file_size_before = main_log_file.stat().st_size
    time.sleep(1)  # To make sure logs stop growing
    assert main_log_file.stat().st_size == main_log_file_size_before
    with server.downloaded_log_files() as downloaded_logs:
        files_from_fs = {log.name: log.stat().st_size for log in downloaded_logs}
    with server.api.all_logs_extracted() as extracted_logs:
        files_from_api = {log.name: log.stat().st_size for log in extracted_logs}
    assert files_from_fs == files_from_api
    with server.downloaded_log_files('main.log') as downloaded_main_log:
        [main_log_file_from_fs] = downloaded_main_log
        with server.api.main_log_extracted() as extracted_main_log:
            assert main_log_file_from_fs.stat().st_size == extracted_main_log.stat().st_size
