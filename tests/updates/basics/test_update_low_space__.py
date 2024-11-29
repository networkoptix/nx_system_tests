# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.updates.common import platforms


def _test_update_low_space(distrib_url, one_vm_type, api_version, exit_stack):
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
    api = one_mediaserver.api()
    api.setup_local_system()
    mediaserver.os_access.maintain_free_disk_space(20 * 1024 * 1024)
    # Release used space after the test, otherwise, it could disrupt log collection
    exit_stack.callback(mediaserver.os_access.clean_up_disk_space)
    update_server = UpdateServer(update_archive, one_mediaserver.os_access().source_address())
    exit_stack.enter_context(update_server.serving())
    api.start_update(update_server.update_info())
    [status] = api.get_update_status().values()
    assert status[api.update_status_literal] == 'error'
    assert status[api.update_error_literal] == 'noFreeSpaceToDownload'
