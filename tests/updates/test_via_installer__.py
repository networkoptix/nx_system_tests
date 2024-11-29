# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_backup_of_previous_database_is_created(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    [pre_install_backup] = mediaserver.list_database_backups()
    assert pre_install_backup.reason == 'timer'

    newer_installer = updates_supplier.upload_server_installer(mediaserver.os_access)
    mediaserver.run_installer(newer_installer)

    [post_install_backup] = wait_for_truthy(
        lambda: mediaserver.list_database_backups(skip_backups=[pre_install_backup]),
        description="New backup appears after the update",
        )
    assert pre_install_backup.build == post_install_backup.build
    assert post_install_backup.reason == 'update'
