# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from types import SimpleNamespace

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from directories.prerequisites import PrerequisiteStore
from installation import ClassicInstallerSupplier
from mediaserver_api import log_full_info_diff
from mediaserver_api import wait_for_servers_synced
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import copy_file
from tests.waiting import wait_for_truthy


def _test_backup_restore(distrib_url, two_vm_types, api_version, db_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    make_server(default_prerequisite_store, 'one', one, db_version)
    two = two_mediaservers.second.installation()
    make_server(default_prerequisite_store, 'two', two, db_version)
    artifacts_dir = get_run_dir()
    merge_systems(two, one, take_remote_settings=False)
    _logger.info("Waiting for servers synchronized after merge")
    wait_for_servers_synced(artifacts_dir, [one, two])
    full_info_initial = one.api.get_full_info()
    backup = one.api.dump_database()
    [camera] = two.api.add_test_cameras(0, 1)
    assert two.api.get_camera(camera.id) is not None
    _logger.info("Waiting for servers synchronized after adding camera")
    wait_for_servers_synced(artifacts_dir, [one, two])
    full_info_with_new_camera = one.api.get_full_info()
    assert two.api.get_camera(camera.id) is not None
    assert one.api.get_camera(camera.id) is not None
    assert full_info_with_new_camera != full_info_initial, (
        "Full server information before and after saveCamera should not match")
    with one.api.waiting_for_restart(timeout_sec=120):
        with two.api.waiting_for_restart(timeout_sec=120):
            one.api.restore_database(backup)
    wait_for_truthy(
        _server_is_connected_to_another_one, args=[two.api, one.get_mediaserver_guid()])
    wait_for_truthy(check_camera_absence_on_server, args=(one, camera.id))
    _logger.info("Waiting for servers synchronized after restore database")
    wait_for_servers_synced(artifacts_dir, [one, two])
    full_info_after = one.api.get_full_info()
    diff_list = full_info_initial.diff(full_info_after)
    _logger.info('Full-info diffs:')
    log_full_info_diff(_logger.info, diff_list)
    assert not diff_list, (
        "Full server information before and after restoreDatabase are not the same.")


_logger = logging.getLogger(__name__)

PREREQUISITES_DIR = 'backup-restore-test'

SERVER_CONFIG = dict(
    one=SimpleNamespace(
        DATABASE_FILE_V_2_4='v2.4.1-box1.db',
        CAMERA_GUID='{ed93120e-0f50-3cdf-39c8-dd52a640688c}',
        SERVER_GUID='{62a54ada-e7c7-0d09-c41a-4ab5c1251db8}',
        ),
    two=SimpleNamespace(
        DATABASE_FILE_V_2_4='v2.4.1-box2.db',
        CAMERA_GUID='{a6b88c1b-92c3-0c27-b5a1-76a1246fd9ed}',
        SERVER_GUID='{88b807ab-0a0f-800e-e2c3-b640b31f3a1c}',
        ),
    )


def _camera_capabilities_appear(mediaserver, camera_id):
    camera = mediaserver.api.get_camera(camera_id)
    return camera.has_capabilities


def make_server(
        prerequisite_store: PrerequisiteStore,
        name,
        mediaserver,
        db_version,
        ):
    server_config = SERVER_CONFIG[name]
    if db_version == '2.4':
        mediaserver.update_conf({
            'guidIsHWID': 'no',
            'serverGuid': server_config.SERVER_GUID,
            })
        db_path = prerequisite_store.fetch(
            '/'.join([PREREQUISITES_DIR, server_config.DATABASE_FILE_V_2_4]))
        copy_file(db_path, mediaserver.ecs_db)
    mediaserver.start()
    mediaserver.api.setup_local_system({'autoDiscoveryEnabled': 'false'})
    mediaserver.api.disable_statistics()
    if db_version == '2.4':
        assert mediaserver.api.get_camera(server_config.CAMERA_GUID) is not None
        # Sometimes it takes time to set the value of the camera capabilities parameter.
        # Thus, there is a need to wait for the value to appear to ensure
        # that the full info dict before and after recovery is the same
        wait_for_truthy(
            _camera_capabilities_appear,
            args=(mediaserver, server_config.CAMERA_GUID),
            description=(
                f"Waiting for capabilities for camera {server_config.CAMERA_GUID} "
                f"to appear in full info"),
            timeout_sec=60)
    return mediaserver


def check_camera_absence_on_server(server, camera_guid):
    return server.api.get_camera(camera_guid) is None


def _server_is_connected_to_another_one(server_api, another_server_guid):
    another_server_info = server_api.get_server(another_server_guid)
    try:
        return another_server_info.status == 'Online'
    # Sometimes the another_server_info may be None because the server can lose connection
    # with an another server after database restore.
    except AttributeError:
        return False
