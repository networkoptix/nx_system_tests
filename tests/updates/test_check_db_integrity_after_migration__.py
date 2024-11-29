# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sqlite3
import tempfile
import time
from contextlib import ExitStack
from contextlib import closing
from pathlib import Path

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import UpdateServer
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import RemotePath
from os_access import copy_file
from tests.updates.common import platforms


def _test_check_db_integrity_after_update(
        release_distrib_url: str, distrib_url: str, exit_stack: ExitStack):
    os_name = 'ubuntu22'
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    installer_supplier_release = ClassicInstallerSupplier(release_distrib_url)
    installer_supplier_release.distrib().assert_can_update_to(installer_supplier.distrib().version())
    pool = FTMachinePool(installer_supplier_release, get_run_dir(), 'v0')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver(os_name))
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.disable_update_files_verification()
    mediaserver.enable_optional_plugins(['stub'])
    mediaserver.start()
    license_server = exit_stack.enter_context(LocalLicenseServer().serving())
    api = mediaserver_stand.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    camera_server = MultiPartJpegCameraServer()
    [camera] = add_cameras(mediaserver, camera_server)
    engine_collection = api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Object Detection')
    with api.camera_recording(camera.id), camera_server.async_serve():
        api.enable_device_agent(engine, camera.id)
        time.sleep(120)
    db_file = mediaserver.list_object_detection_db()[api.get_server_id()]
    db_file_local = get_run_dir() / f'{db_file.stem}_{api.get_version().as_str}{db_file.suffix}'
    mediaserver.stop()
    copy_file(db_file, db_file_local)
    mediaserver.start()
    tracks_before = api.list_analytics_objects_tracks()
    update_archive = installer_supplier.fetch_server_updates([platforms[os_name]])
    update_server = UpdateServer(update_archive, mediaserver_stand.os_access().source_address())
    exit_stack.enter_context(update_server.serving())
    api.prepare_update(update_server.update_info())
    with api.waiting_for_restart(timeout_sec=120):
        api.install_update()
    assert api.get_version() == installer_supplier.distrib().version()
    started_at = time.monotonic()
    while True:
        # /ec2/analyticsLookupObjectTracks may not return all tracks immediately after starting.
        tracks_after = api.list_analytics_objects_tracks()
        if len(tracks_after) == len(tracks_before):
            break
        if time.monotonic() - started_at > 10:
            mediaserver.stop()
            tracks_count_in_db = _get_tracks_count_from_database(db_file)
            raise RuntimeError(
                f"Before the update, there were {len(tracks_before)} tracks; "
                f"after the update, there are {len(tracks_after)}. "
                f"The 'track' table of the analytic database contains {tracks_count_in_db} tracks")
        time.sleep(1)


def _get_tracks_count_from_database(remote_object_detection_db_file: RemotePath) -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        local_db_file = Path(tmpdir) / remote_object_detection_db_file.name
        copy_file(remote_object_detection_db_file, local_db_file)
        db_connection = sqlite3.connect(local_db_file)
        with closing(db_connection), closing(db_connection.cursor()) as db_cursor:
            res = db_cursor.execute('SELECT count(1) FROM track')
            [track_count] = res.fetchone()
        return int(track_count)
