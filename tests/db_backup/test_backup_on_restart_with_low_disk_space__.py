# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
import time

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import WindowsAccess
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_backup_on_restart_with_low_disk_space(distrib_url, one_vm_type, api_version, backup_period_sec, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    if isinstance(one_mediaserver.os_access(), WindowsAccess):
        one_mediaserver.os_access().disable_netprofm_service()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'dbBackupPeriodMS': backup_period_sec * 1000})
    mediaserver.remove_database_backups()
    database_file = default_prerequisite_store.fetch("backup-restore-test/ecs.sqlite")
    mediaserver.replace_database(database_file)
    mediaserver.start()
    mediaserver.api.setup_local_system()
    mediaserver.remove_database_backups()
    MAX_BACKUPS = 6
    wait_for_truthy(
        _meet_expected_backup_count,
        args=(mediaserver, MAX_BACKUPS, mediaserver.os_access),
        description="maximum backups created",
        timeout_sec=backup_period_sec * MAX_BACKUPS + 60,
        )
    old_backups_before_rotation = mediaserver.list_database_backups()
    backup_size_bytes = old_backups_before_rotation[0].size()
    backups_to_delete = 2
    low_space_threshold = 10 * 1024**3
    free_space_bytes = int(
        low_space_threshold - backups_to_delete * backup_size_bytes + 0.5 * backup_size_bytes)
    mediaserver.stop()
    mediaserver.os_access.maintain_free_disk_space(free_space_bytes)
    assert mediaserver.os_access.system_disk().free < low_space_threshold
    mediaserver.start()
    mediaserver.wait_for_database_backups(
        skip_backups=old_backups_before_rotation,
        # Wait for additional time because server start can delay period timer.
        timeout_sec=backup_period_sec * 1.5,
        )
    wait_for_truthy(
        _meet_expected_backup_count,
        args=(mediaserver, MAX_BACKUPS - backups_to_delete, mediaserver.os_access),
        description="backups rotated",
        timeout_sec=backup_period_sec,
        )
    [*old_backups_after_rotation, new_backup] = mediaserver.list_database_backups()
    assert new_backup not in old_backups_before_rotation
    assert all(backup in old_backups_before_rotation for backup in old_backups_after_rotation)
    time.sleep(backup_period_sec / 2)
    wait_for_truthy(
        _meet_expected_backup_count,
        args=(mediaserver, MAX_BACKUPS - backups_to_delete, mediaserver.os_access),
        description="backups rotated",
        timeout_sec=5,
        )
    free_space = mediaserver.os_access.system_disk().free
    assert math.isclose(free_space, low_space_threshold, abs_tol=backup_size_bytes)


def _meet_expected_backup_count(server, expected_backups_count, os):
    current_backups = server.api.list_db_backups()
    free_space_bytes = os.system_disk().free
    _logger.debug("Current backups (%d): %r", len(current_backups), current_backups)
    _logger.debug("Free space: %d bytes", free_space_bytes)
    return len(current_backups) == expected_backups_count
