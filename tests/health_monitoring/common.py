# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools

from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import Mediaserver
from mediaserver_api import Permissions
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.software_camera_scenarios import add_cameras

_global_camera_offset = itertools.count()
_global_suffix = itertools.count()


def _suffix():
    return str(next(_global_suffix))


def add_group(mediaserver):
    return mediaserver.api.add_user_group(
        f'custom_group{_suffix()}',
        ['GlobalManageBookmarksPermission', 'GlobalUserInputPermission'])


def add_users_and_group(mediaserver):
    custom_group_id = add_group(mediaserver)
    users = [
        {"name": "test_admin", "permissions": [Permissions.ADMIN]},
        {"name": "test_live_viewer", "permissions": [Permissions.ACCESS_ALL_MEDIA]},
        {"name": "test_viewer", "permissions": Permissions.VIEWER_PRESET},
        {"name": "test_advanced_viewer", "permissions": Permissions.ADVANCED_VIEWER_PRESET},
        {"name": "test_custom_permissions", "permissions": [Permissions.CUSTOM_USER]},
        {"name": "test_custom_group", "group_id": custom_group_id},
        ]

    return [
        mediaserver.api.add_local_user(
            password="irrelevant",
            name=user.pop('name') + _suffix(),
            **user)
        for user in users]


def add_test_cameras(mediaserver, cameras_count=1):
    offset_list = list(itertools.islice(_global_camera_offset, cameras_count))
    offset = offset_list.pop(0)
    cameras = mediaserver.api.add_test_cameras(offset, cameras_count)
    return [camera.id for camera in cameras]


def configure_mediaserver_with_mjpeg_cameras(
        license_server: LocalLicenseServer,
        mediaserver: Mediaserver,
        camera_count: int,
        ):
    mediaserver.start(already_started_ok=True)
    with license_server.serving():
        mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
        grant_license(mediaserver, license_server)
    camera_server = MultiPartJpegCameraServer()
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    return camera_server, cameras
