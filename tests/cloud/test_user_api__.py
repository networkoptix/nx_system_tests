# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_cloud_users(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = stand.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    api = stand.api()
    api.setup_cloud_system(cloud_account)
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    second_cloud_user_email = second_cloud_account.user_email
    cloud_user_id = api.add_cloud_user(
        name=second_cloud_user_email,
        permissions=[Permissions.ADMIN],
        email=second_cloud_user_email,
        )
    cloud_user = api.get_user(cloud_user_id)
    assert cloud_user is not None, f"Cloud user {cloud_user_id} is not found."
    assert cloud_user.is_cloud
    assert cloud_user.is_enabled
    all_users = api.list_users()
    assert cloud_user in all_users
    api.remove_user(cloud_user_id)
    assert api.get_user(cloud_user_id) is None
