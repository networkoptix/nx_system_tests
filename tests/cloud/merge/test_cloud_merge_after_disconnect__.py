# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.merge.common import TEST_SYSTEM_SETTINGS
from tests.cloud.merge.common import wait_for_settings_merge


def _test_cloud_merge_after_disconnect(cloud_host, distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    one.allow_access_to_cloud(cloud_host)
    one.set_cloud_host(cloud_host)
    one.start()
    one.api.setup_cloud_system(cloud_account, TEST_SYSTEM_SETTINGS)
    two.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    two.allow_access_to_cloud(cloud_host)
    two.set_cloud_host(cloud_host)
    two.start()
    two.api.setup_cloud_system(cloud_account)
    # Check setupCloud's settings on Server1
    settings_to_check = {
        k: v for k, v in one.api.get_system_settings().items() if k in TEST_SYSTEM_SETTINGS.keys()}
    assert settings_to_check == TEST_SYSTEM_SETTINGS
    # Disconnect Server2 from cloud
    new_password = 'new_password'
    two.api.detach_from_cloud(new_password, cloud_account.password)
    if api_version == 'v0':
        # Admin settings are reset after disconnecting the system from the cloud.
        # Therefore, Basic and Digest authentication should be re-enabled.
        two.api.enable_basic_and_digest_auth_for_admin()
    # Merge systems (takeRemoteSettings = true)
    merge_systems(two, one, take_remote_settings=True)
    wait_for_settings_merge(one, two)
    # Ensure both servers are merged and sync
    audit_trail_enabled = one.api.get_system_settings()['auditTrailEnabled']
    expected_audit_trail_enabled = 'true' if audit_trail_enabled == 'false' else 'false'
    one.api.set_system_settings({'auditTrailEnabled': expected_audit_trail_enabled})
    wait_for_settings_merge(one, two)
    assert two.api.get_system_settings()['auditTrailEnabled'] == expected_audit_trail_enabled
