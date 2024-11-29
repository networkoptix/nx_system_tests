# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_backup_by_schedule(distrib_url, one_vm_type, api_version, backup_period_sec, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'dbBackupPeriodMS': backup_period_sec * 1000})
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    mediaserver.remove_database_backups()
    # FT-459
    mediaserver.wait_for_database_backups(timeout_sec=backup_period_sec)

    # FT-460
    start_time = time.monotonic()

    MAX_BACKUPS = 6

    # For now we already have 1 backup
    while time.monotonic() - start_time < backup_period_sec * MAX_BACKUPS:
        if len(mediaserver.list_database_backups()) == MAX_BACKUPS:
            break
        time.sleep(backup_period_sec / 10)
    else:
        raise RuntimeError("Number of backups has not reached {}".format(MAX_BACKUPS))

    start_time = time.monotonic()
    backups = mediaserver.list_database_backups()
    mediaserver.wait_for_database_backups(skip_backups=backups)
    # FT-1626: After the new db backup file occurred and before the
    # oldest file is removed, there is a small period of time when there
    # are MAX_BACKUPS + 1 files. We should wait more than this period of
    # time.
    backup_rotation_delay = 0.1
    time.sleep(backup_rotation_delay)
    assert len(mediaserver.list_database_backups()) == MAX_BACKUPS

    # FT-467
    backups = mediaserver.list_database_backups()
    mediaserver.os_access.maintain_free_disk_space(9 * 1024**3)
    wait_for_truthy(
        lambda: len(mediaserver.list_database_backups()) == 1,
        description="Create single backup",
        )
    [single_backup] = mediaserver.list_database_backups()
    assert single_backup not in backups
