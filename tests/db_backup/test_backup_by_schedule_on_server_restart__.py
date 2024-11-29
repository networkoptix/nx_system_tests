# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_backup_by_schedule_on_server_restart(distrib_url, one_vm_type, api_version, backup_period_sec, exit_stack):
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
    [first_backup] = mediaserver.wait_for_database_backups(timeout_sec=backup_period_sec)
    start_time = time.monotonic()
    mediaserver.stop()
    mediaserver.start()
    mediaserver.wait_for_database_backups(
        skip_backups=[first_backup],
        timeout_sec=backup_period_sec - (time.monotonic() - start_time),
        )