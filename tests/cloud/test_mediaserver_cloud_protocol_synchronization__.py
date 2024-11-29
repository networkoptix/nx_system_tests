# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_mediaserver_cloud_protocol_synchronization(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
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
    mediaserver.api.setup_cloud_system(cloud_account)
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    second_cloud_user_email = second_cloud_account.user_email
    mediaserver.api.add_cloud_user(
        name=second_cloud_user_email,
        permissions=[Permissions.ADMIN],
        email=second_cloud_user_email,
        )

    users = mediaserver.api.list_users()
    second_cloud_users = [u for u in users if u.name == second_cloud_user_email]
    assert len(second_cloud_users) == 1  # One second cloud user is expected
    assert second_cloud_users[0].is_enabled
    assert second_cloud_users[0].is_cloud

    cloud_user_api = mediaserver.api.with_credentials(
        second_cloud_user_email,
        second_cloud_account.password,
        )
    # If synchronization protocols mismatch then second cloud user information
    # will never make it to the cloud. And, as a result, the user will never
    # be able to login to the mediaserver. At the moment, the synchronization
    # period is about 30 second.
    wait_for_truthy(cloud_user_api.credentials_work, timeout_sec=60)
