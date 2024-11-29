# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import wait_for_servers_info_synced
from mediaserver_api import wait_until_no_transactions
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_merge_and_change_cloud_host(distrib_url, two_vm_types, api_version, take_remote_settings, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    servers = [one, two]
    fake_cloud_host = 'cloud.non.existent'
    for server in servers:
        server.set_cloud_host(fake_cloud_host)
        server.start()
        server.api.setup_local_system()
    resource_ids = itertools.count(1)  # Ensures that id values stay unique.
    one.api.add_test_cameras(next(resource_ids), 1)
    one.api.add_local_user("test_user_first_server", "irrelevant")
    two.api.add_test_cameras(next(resource_ids), 1)
    two.api.add_local_user("test_user_second_server", "irrelevant")
    cameras_one_before = one.api.list_cameras()
    users_one_before = one.api.list_users()
    cameras_two_before = two.api.list_cameras()
    merge_systems(one, two, take_remote_settings=take_remote_settings)
    cameras_one_after_merge = one.api.list_cameras()
    users_one_after_merge = one.api.list_users()
    assert len(cameras_one_after_merge) == len(cameras_one_before) + len(cameras_two_before), (
        f"Wrong number of cameras after merge, "
        f"expected {len(cameras_one_before) + len(cameras_two_before)}, "
        f"got {len(cameras_one_after_merge)}")
    assert len(users_one_after_merge) == len(users_one_before) + 1, (
        f"Wrong number of users after merge, "
        f"expected {len(users_one_before) + 1}, "
        f"got {len(users_one_after_merge)}")
    assert two.api.list_cameras() == cameras_one_after_merge
    assert two.api.list_users() == users_one_after_merge
    one.api.add_test_cameras(next(resource_ids), 1)
    two.api.add_local_user("test_user_after_merge", "irrelevant")
    for server in servers:
        server.stop(already_stopped_ok=True)
        server.start()
    cameras_one_after_merge_one_added = two.api.list_cameras()
    users_one_after_merge_one_added = two.api.list_users()
    assert cameras_one_after_merge_one_added == two.api.list_cameras()
    assert len(cameras_one_after_merge_one_added) == len(cameras_one_after_merge) + 1
    assert users_one_after_merge_one_added == two.api.list_users()
    assert len(users_one_after_merge_one_added) == len(users_one_after_merge) + 1
    # After starting mediaserver, it may take some time to synchronize with other mediaservers on the system.
    # Without this synchronization, session authorization might not work.
    wait_until_no_transactions(one.api, silence_sec=3, timeout_sec=10)
    two.api.add_test_cameras(next(resource_ids), 1)
    one.api.add_local_user("test_user_after_no_transaction", "irrelevant")
    wait_for_servers_info_synced(servers)
