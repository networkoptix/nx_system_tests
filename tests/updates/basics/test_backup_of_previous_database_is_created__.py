# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.updates.common import platforms
from tests.waiting import wait_for_truthy


def _test_backup_of_previous_database_is_created(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    update_archive = updates_supplier.fetch_server_updates([platforms[one_vm_type]])
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.disable_update_files_verification()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    # Disable time sync to allow manipulate the date.
    mediaserver.api.disable_time_sync()
    [pre_update_backup] = mediaserver.list_database_backups()
    assert pre_update_backup.reason == 'timer'

    update_server = UpdateServer(update_archive, one_mediaserver.os_access().source_address())
    exit_stack.enter_context(update_server.serving())
    update_info = update_server.update_info()
    mediaserver.api.prepare_update(update_info)
    with mediaserver.api.waiting_for_restart(timeout_sec=120):
        mediaserver.api.install_update()

    [post_update_backup] = wait_for_truthy(
        lambda: mediaserver.list_database_backups(skip_backups=[pre_update_backup]),
        description="New backup appears after the update",
        )
    assert pre_update_backup.build == post_update_backup.build
    assert post_update_backup.reason == 'update'
    mediaserver.stop()
    mediaserver.start()
    time.sleep(10)
    assert not mediaserver.list_database_backups(skip_backups=[pre_update_backup, post_update_backup])
    mediaserver.os_access.shift_time(timedelta(days=7))
    # Mediaserver updates a timer that counts down to the next database backup at startup.
    mediaserver.stop()
    mediaserver.start()
    [new_version_backup] = wait_for_truthy(
        lambda: mediaserver.list_database_backups(skip_backups=[pre_update_backup, post_update_backup]),
        description="New backup appeared after changing the time",
        timeout_sec=60,
        )
    assert new_version_backup.build == update_archive.version().build
    assert new_version_backup.reason == 'timer'
