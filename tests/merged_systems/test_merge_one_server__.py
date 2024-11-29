# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_equal


def _test_merge_one_server_from_the_system(distrib_url, merge_with_second, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    # Special configuration to check two system merge.
    # The first system contains only one mediaserver,
    # the second contains two merged mediaservers.
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'networks': {
            '10.254.0.0/28': {
                'first': None,
                'second': None,
                'third': None,
                },
            },
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'ubuntu22'},
            {'alias': 'third', 'type': 'ubuntu22'},
            ],
        'mergers': [],
        }))
    [system, _, _] = network_and_system
    mediaservers = system.values()
    [one, two, three] = mediaservers
    first_system_password = 'Test1'
    second_system_password = 'Test2'
    _set_password(one, first_system_password)
    _set_password(two, second_system_password)
    _set_password(three, second_system_password)
    if api_version == 'v0':
        # Updating server password requires re-enabling Basic and Digest authentication.
        one.api.enable_basic_and_digest_auth_for_admin()
        two.api.enable_basic_and_digest_auth_for_admin()
        three.api.enable_basic_and_digest_auth_for_admin()
    merge_systems(two, three, take_remote_settings=False)
    two.api.wait_for_neighbors_status('Online', timeout_sec=30)
    three.api.wait_for_neighbors_status('Online', timeout_sec=30)
    if merge_with_second:
        # We need to test that order of previous merge does
        # not affect the current merge.
        # See: https://networkoptix.testrail.net/index.php?/cases/view/81206
        [three, two] = [two, three]
    server_one_data_before = one.api.get_server_info()
    server_two_data_before = two.api.get_server_info()
    server_three_data_before = three.api.get_server_info()
    assert _server_info_matches(server_two_data_before, server_three_data_before)
    audit_trail = one.api.audit_trail()
    merge_systems(one, two, take_remote_settings=False, merge_one_server=True)
    # Since the second server is no longer on the same system as the third server,
    # the third server should not use the remote auth handler (from the second server).
    three.api.use_local_auth()
    record = audit_trail.wait_for_one()
    assert record.type == one.api.audit_trail_events.SITES_MERGE
    one_guid = one.api.get_server_id()
    two_guid = two.api.get_server_id()
    three_guid = three.api.get_server_id()
    wait_for_equal(
        one.api.list_system_mediaservers_status,
        {one_guid: 'Online', two_guid: 'Online', three_guid: 'Offline'},
        )
    wait_for_equal(
        two.api.list_system_mediaservers_status,
        {one_guid: 'Online', two_guid: 'Online', three_guid: 'Offline'},
        )
    wait_for_equal(
        three.api.list_system_mediaservers_status,
        {two_guid: 'Offline', three_guid: 'Online'},
        )
    server_one_data_after = one.api.get_server_info()
    server_two_data_after = two.api.get_server_info()
    server_three_data_after = three.api.get_server_info()
    assert _server_info_matches(server_one_data_after, server_one_data_before)
    assert not _server_info_matches(server_two_data_after, server_two_data_before)
    assert _server_info_matches(server_two_data_after, server_one_data_before)
    assert not _server_info_matches(server_one_data_after, server_three_data_after)
    assert _server_info_matches(server_three_data_after, server_three_data_before)
    assert one.api.with_password(first_system_password).credentials_work()
    assert not two.api.with_password(second_system_password).credentials_work()
    assert two.api.with_password(first_system_password).credentials_work()
    assert three.api.with_password(second_system_password).credentials_work()


def _server_info_matches(
        first_info: MediaserverApi.MediaserverInfo,
        second_info: MediaserverApi.MediaserverInfo) -> bool:
    first = (first_info.local_site_id, first_info.site_name)
    second = (second_info.local_site_id, second_info.site_name)
    return first == second


def _set_password(mediaserver, password):
    mediaserver.stop()
    mediaserver.update_conf({'appserverPassword': password})
    mediaserver.api.set_password(password)
    mediaserver.start()
