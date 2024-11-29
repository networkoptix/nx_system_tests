# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


# See: https://networkoptix.atlassian.net/browse/CLOUD-1114
def _test_merge_cloud_systems_with_same_owner(cloud_host, distrib_url, two_vm_types, api_version, take_remote_settings, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    for server in one, two:
        server.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
        server.allow_access_to_cloud(cloud_host)
        server.set_cloud_host(cloud_host)
        server.start()
        server.api.setup_cloud_system(cloud_account)
    # Merge 2 cloud systems one way
    merge_systems(one, two, take_remote_settings=take_remote_settings)
