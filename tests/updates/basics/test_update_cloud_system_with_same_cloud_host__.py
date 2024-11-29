# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import Skip
from tests.updates.common import platforms


def _test_update_cloud_system_with_same_cloud_host(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_branch_not_mobile()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = distrib.customization().customization_name
    cloud_account.set_user_customization(customization_name)
    distrib.assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    distrib.assert_updates_support("Update testing is not supported for release builds")
    updates_supplier = installer_supplier.update_supplier()
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    update_archive = updates_supplier.fetch_server_updates([platforms[one_vm_type]])
    # Basically, this is simple update test.
    if updates_supplier.distrib().customization() != distrib.customization():
        raise Skip("Both versions must have same customization")
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.disable_update_files_verification()
    mediaserver.start()
    mediaserver.api.setup_cloud_system(cloud_account)
    update_server = UpdateServer(update_archive, one_mediaserver.os_access().source_address())
    exit_stack.enter_context(update_server.serving())
    mediaserver.api.prepare_update(update_server.update_info())
    with mediaserver.api.waiting_for_restart(timeout_sec=120):
        mediaserver.api.install_update()
    assert mediaserver.api.get_version() == updates_supplier.distrib().version()
