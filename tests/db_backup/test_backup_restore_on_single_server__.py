# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_api import generate_layout
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.waiting import wait_for_truthy


def _test_restore_from_scheduled_backup(distrib_url, one_vm_type, api_version, backup_period_sec, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'dbBackupPeriodMS': backup_period_sec * 1000})
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    mediaserver.remove_database_backups()
    artifacts_dir = get_run_dir()
    _populate_database(mediaserver, license_server)
    mediaserver.remove_database_backups()
    [backup_file] = mediaserver.wait_for_database_backups(timeout_sec=10)
    backup_file_contents = backup_file.content()
    backup_via_api = mediaserver.api.dump_database()
    full_info_original = mediaserver.api.get_full_info()

    _reset_database(mediaserver, artifacts_dir)
    assert full_info_original != mediaserver.api.get_full_info()
    with mediaserver.api.waiting_for_restart():
        mediaserver.api.restore_database(backup_file_contents)
    assert mediaserver.api.credentials_work()
    wait_for_truthy(_restored_server_info_matches, args=(mediaserver, full_info_original))

    _reset_database(mediaserver, artifacts_dir)
    assert full_info_original != mediaserver.api.get_full_info()
    with mediaserver.api.waiting_for_restart():
        mediaserver.api.restore_database(backup_via_api)
    assert mediaserver.api.credentials_work()
    wait_for_truthy(_restored_server_info_matches, args=(mediaserver, full_info_original))


_logger = logging.getLogger(__name__)


def _populate_database(server, license_server):
    # Activate license.
    brand = server.api.get_brand()
    digital_key = license_server.generate({'BRAND2': brand})
    server.api.activate_license(digital_key)
    videowall_key = license_server.generate({'BRAND2': brand, 'CLASS2': 'videowall'})
    server.api.activate_license(videowall_key)

    # Populate DB with a valid user.
    username = 'test_user'
    password = 'WellKnownPassword1'  # noqa SpellCheckingInspection
    user = server.api.add_local_admin(username, password)
    user_api = server.api.as_user(user)
    assert user_api.credentials_work()

    # Add layout to user.
    generated_layout = generate_layout(index=1, parent_id=str(user.id))
    server.api.add_generated_layout(generated_layout)

    # Change password for admin.
    server.api.change_admin_password('ADMIN123')
    assert server.api.credentials_work()

    camera_server = MjpegRtspCameraServer()
    [camera] = add_cameras(server, camera_server)

    [default_storage] = server.api.list_storages()
    # Populate DB with a couple of storages.
    storage_one_path = server.os_access.mount_fake_disk('E', 11 * 1024**3)
    storage_two_path = server.os_access.mount_fake_disk('F', 11 * 1024**3)
    server.stop()
    server.start()
    [storage_one] = server.api.list_storages(str(storage_one_path))
    [storage_two] = server.api.list_storages(str(storage_two_path))
    # Unset "isUsedForWriting" from all storages.
    server.api.disable_storage(default_storage.id)
    server.api.disable_storage(storage_one.id)
    server.api.disable_storage(storage_two.id)

    # Set recording for camera.
    server.api.start_recording(camera.id)

    # Create video wall and add screens to video wall.
    server.api.add_videowall(name='FT_224_videowall')

    # Set non-default values to general system settings.
    server.api.set_system_settings({
        'autoDiscoveryEnabled': 'False',
        'cameraSettingsOptimization': 'False',
        'statisticsAllowed': 'False',
        })

    server.api.set_email_settings(
        email='nx@gmail.com',
        connection_type='Tls',
        server='smtp.gmail.com',
        password='WellKnownPassword1',
        user='nx@gmail.com',
        )

    # Add event rule.
    server.api.add_event_rule(
        event_type=EventType.SERVER_START,
        event_state=EventState.ACTIVE,
        action=RuleAction('showTextOverlayAction'),
        )
    return server


def _reset_database(server, artifacts_dir):
    server.stop()
    artifacts_before_reset_dir = artifacts_dir / 'before_reset'
    artifacts_before_reset_dir.mkdir(exist_ok=True)
    server.collect_artifacts(artifacts_before_reset_dir)
    server.remove_database()
    server.remove_database_backups()
    server.api.reset_credentials()
    server.start()
    server.api.setup_local_system()


def _restored_server_info_matches(server, expected_full_info):
    diff_list = server.api.get_full_info().diff(expected_full_info)
    # These fields change after the database is restored.
    expected_diffs = [
        r'servers/[a-zA-Z0-9-]*/parameters/certificate',
        r'servers/[a-zA-Z0-9-]*/parameters/userProvidedCertificate',
        ]
    expected_diffs = '|'.join(expected_diffs)
    diff_list = {k: v for k, v in diff_list.items() if not re.match(expected_diffs, k)}
    return not diff_list
