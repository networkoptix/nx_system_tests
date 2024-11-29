# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ca import default_ca
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import public_ip_check_addresses
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.merge.common import TEST_SYSTEM_SETTINGS
from tests.cloud.merge.common import wait_for_settings_merge


def configure_server_with_test_settings(server: Mediaserver, cloud_host):
    server.set_cloud_host(cloud_host)
    server.start()
    server.api.setup_local_system(TEST_SYSTEM_SETTINGS)


def configure_server_with_cloud_access(server: Mediaserver, cloud_host):
    server.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    server.allow_access_to_cloud(cloud_host)
    server.set_cloud_host(cloud_host)
    server.start()
    server.api.setup_local_system()


def _test_restart_one_server(cloud_host, distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    configure_server_with_test_settings(one, cloud_host)
    configure_server_with_cloud_access(two, cloud_host)
    merge_systems(one, two, take_remote_settings=False)
    one.api.wait_for_neighbors_status('Online')
    # Stop Server2 and clear its database
    guid2 = two.api.get_server_id()
    two.stop()
    two.remove_database()
    two.remove_database_backups()
    two.init_key_pair(default_ca().generate_key_and_cert(two.os_access.address))
    two.set_cloud_host(cloud_host)
    one.api.wait_for_neighbors_status('Offline')
    two.start()
    # Remove Server2 from database on Server1
    one.api.remove_server(guid2)
    # Restore initial REST API
    two.api.reset_credentials()
    # Start server 2 again and move it from initial to working state
    two.api.setup_cloud_system(cloud_account)
    # Here merge between mediaservers takes much longer than usual.
    # Possible reason is cloud accounts are used.
    merge_timeout_sec = 120
    merge_systems(two, one, take_remote_settings=False, timeout_sec=merge_timeout_sec)
    # Ensure both servers are merged and sync
    rtsp_enabled = one.api.get_system_settings()['arecontRtspEnabled']
    expected_rtsp_enabled = 'true' if rtsp_enabled == 'false' else 'false'
    one.api.set_system_settings({'arecontRtspEnabled': expected_rtsp_enabled})
    wait_for_settings_merge(one, two)
    assert two.api.get_system_settings()['arecontRtspEnabled'] == expected_rtsp_enabled
