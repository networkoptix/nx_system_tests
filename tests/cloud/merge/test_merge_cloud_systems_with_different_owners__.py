# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import CloudSystemsHaveDifferentOwners
from mediaserver_api import Forbidden
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def check_admin_disabled(server):
    users = server.api.list_users()
    admin_users = [u for u in users if u.name == 'admin']
    assert len(admin_users) == 1  # One Cloud user is expected
    assert not admin_users[0].is_enabled
    with assert_raises(Forbidden):
        server.api.enable_user(admin_users[0].id)


# See: https://networkoptix.atlassian.net/browse/CLOUD-1114
def _test_merge_cloud_systems_with_different_owners(cloud_host, distrib_url, two_vm_types, api_version, take_remote_settings, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account_1 = cloud_account_factory.create_account()
    cloud_account_2 = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account_1.set_user_customization(customization_name)
    cloud_account_2.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    one.allow_access_to_cloud(cloud_host)
    one.set_cloud_host(cloud_host)
    one.start()
    one.api.setup_cloud_system(cloud_account_1)
    two.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    two.allow_access_to_cloud(cloud_host)
    two.set_cloud_host(cloud_host)
    two.start()
    two.api.setup_cloud_system(cloud_account_2)
    # Merge 2 Cloud systems one way.
    with assert_raises(CloudSystemsHaveDifferentOwners):
        merge_systems(one, two, take_remote_settings=take_remote_settings)
    # Test default (admin) user disabled.
    check_admin_disabled(one)
