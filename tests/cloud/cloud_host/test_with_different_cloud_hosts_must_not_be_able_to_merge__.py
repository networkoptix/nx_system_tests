# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import IncompatibleCloud
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.cloud_host.common import check_user_exists
from tests.infra import assert_raises


def _test_with_different_cloud_hosts_must_not_be_able_to_merge(cloud_host, distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    test_cloud_server = two_mediaservers.first.installation()
    wrong_cloud_server = two_mediaservers.second.installation()

    test_cloud_server.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    test_cloud_server.allow_access_to_cloud(cloud_host)
    test_cloud_server.set_cloud_host(cloud_host)
    test_cloud_server.start()
    test_cloud_server.api.setup_cloud_system(cloud_account)

    wrong_cloud_server.set_cloud_host('cloud.non.existent')
    wrong_cloud_server.start()
    wrong_cloud_server.api.setup_local_system()

    check_user_exists(test_cloud_server, is_cloud=True)

    with assert_raises(IncompatibleCloud):
        merge_systems(test_cloud_server, wrong_cloud_server, take_remote_settings=False)
