# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_disconnected_system_removed_for_cloud_users(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    mediaserver.api.setup_local_system()
    bind_info = cloud_account.bind_system(system_name='Irrelevant')
    mediaserver.api.connect_system_to_cloud(
        bind_info.auth_key, bind_info.system_id, cloud_account.user_email)
    cloud_system_id = mediaserver.api.get_cloud_system_id()
    assert cloud_account.get_system(cloud_system_id) is not None
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    cloud_account.share_system(
        cloud_system_id, second_cloud_account.user_email, user_groups=[Groups.VIEWERS])
    assert second_cloud_account.get_system(cloud_system_id) is not None
    users = mediaserver.api.list_users()
    [cloud_user] = [u for u in users if u.name == cloud_account.user_email]
    credentials = mediaserver.api.get_credentials()
    mediaserver.api.detach_from_cloud(credentials.password, credentials.password)
    # Admin settings are reset after disconnecting the system from the cloud.
    # Therefore, Basic and Digest authentication should be re-enabled.
    mediaserver.api.enable_basic_and_digest_auth_for_admin()
    assert cloud_account.get_system(cloud_system_id) is None
    assert second_cloud_account.get_system(cloud_system_id) is None
    assert mediaserver.api.get_user(cloud_user.id) is None
