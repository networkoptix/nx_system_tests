# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Sequence

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import RemotePath
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_size_limit_setting(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    server = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    server.remove_logging_ini()
    server.set_main_log_level('verbose')
    server.set_max_log_file_size(limit_bytes=50 * 1024 * 1024)
    server.start()
    server.api.setup_local_system()
    [main_log_file] = server.list_log_files('main.log')
    main_log_file_size_before = main_log_file.stat().st_size
    time.sleep(1)
    assert main_log_file_size_before < main_log_file.stat().st_size
    assert not server.list_log_files('*.log.zip')
    max_log_file_size = main_log_file.stat().st_size // 30  # To speed up the test
    server.api.set_max_log_file_size(max_log_file_size)
    log_archives_chain = _get_log_archives_chain(server)
    archives_names = [archive.name for archive in log_archives_chain]
    expected_names = [f'main_{index+1:03d}.log.zip' for index in range(len(archives_names))]
    assert archives_names == expected_names
    archives_mtimes = [archive.stat().st_mtime for archive in log_archives_chain]
    assert archives_mtimes == sorted(archives_mtimes)
    max_log_volume_size = max_log_file_size * 5  # Volume limit must not be less than 5 file limits
    [rotated_log_file, *_] = server.list_log_files('*.log.zip')
    # Make the rotated log file big enough to exceed the volume size limit faster.
    with rotated_log_file.open('rb+') as f:
        f.seek(max_log_volume_size)
        f.write(b'0')
    assert _total_volume_size(server) > max_log_volume_size
    server.api.set_max_log_volume_size(max_log_volume_size)
    wait_for_truthy(
        lambda: _total_volume_size(server) <= max_log_volume_size,
        description="Old rotated log files are removed to fit within the maximum volume size")


def _get_log_archives_chain(api: Mediaserver) -> Sequence[RemotePath]:
    archive_chain_length = 6
    wait_timeout = 90
    logging.info(
        "Waiting %s files for %s seconds to ensure that "
        "archived logs are being accumulated, not rewritten ...",
        archive_chain_length, wait_timeout)
    end_at = time.monotonic() + wait_timeout
    while True:
        log_files = api.list_log_files('*.log.zip')
        logging.info("Log files now: %s", log_files)
        if len(log_files) >= archive_chain_length:
            logging.info("Found %s files: %s", archive_chain_length, log_files)
            return sorted(log_files, key=lambda log_file: log_file.stat().st_mtime)
        if time.monotonic() > end_at:
            raise RuntimeError(
                f"Desired amount of files {archive_chain_length} is not found. "
                f"Current list is {log_files}")
        logging.info("Not enough files: %s. Retrying after 1 sec delay ...", log_files)
        time.sleep(1)


def _total_volume_size(server) -> int:
    # When rotating log files, they are first renamed to *.tmp. There is a chance
    # that at the time of requesting a list of log files, one of them will be
    # in the process of rotation. This will cause the method to return the name
    # of such a temporary file, and later, when the size of this file
    # is requested, it may already be rotated, i.e. missing.
    for _ in range(3):
        log_files = server.list_log_files()
        try:
            return sum(file.stat().st_size for file in log_files)
        except FileNotFoundError as e:
            _logger.info("Race condition: %s. Wait for a while and try again", str(e))
            time.sleep(0.5)
    raise RuntimeError("Cannot read log files. Looks like the logs rotation is in process")
