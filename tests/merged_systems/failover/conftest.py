# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from itertools import zip_longest
from urllib.parse import urlparse

from doubles.dnssd import DNSSDWebService
from doubles.licensing import LicenseServer
from installation import Mediaserver
from mediaserver_scenarios.software_camera_scenarios import MediaserversDNSSDScope


def configure_license(mediaserver: Mediaserver, license_server: LicenseServer):
    mediaserver.allow_license_server_access(license_server.url())
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    mediaserver.api.activate_license(key)


def discover_camera(mediaserver, camera_server, path):
    os = mediaserver.os_access
    local_address = os.source_address()
    service = DNSSDWebService('camera', local_address, camera_server.port, path)
    started_at = time.monotonic()
    server_uuid = mediaserver.api.get_server_id()
    camera_name = f'http://{local_address}:{camera_server.port}{path}'
    scope = MediaserversDNSSDScope([mediaserver])
    while time.monotonic() - started_at < 60:
        scope.advertise_once([service])
        for camera in mediaserver.api.list_cameras():
            if camera.name == camera_name and camera.parent_id == server_uuid:
                return camera
        time.sleep(5.0)
    raise RuntimeError(f"Timed out waiting for discovery camera appear {path}")


def advertise_to_change_camera_parent(cameras, servers, advertising_cameras=None, timeout_sec=120):
    started_at = time.monotonic()
    advertising_cameras = advertising_cameras or cameras
    while time.monotonic() - started_at < timeout_sec:
        # The servers might be unsynced after merge or restart,
        # we have to wait parent_ids for expected camera are equal
        # for all online servers in the system.
        for advertising_camera in advertising_cameras:
            _advertise_to_many(advertising_camera.url, servers)
        time.sleep(5.0)
        result = []
        for camera in cameras:
            camera_from_servers_list = _get_camera_for_servers(camera.id, servers)
            if len(camera_from_servers_list) != len(servers):
                # The system aren't synced yet.
                break
            parent_id_set = set(camera.parent_id for camera in camera_from_servers_list)
            if len(parent_id_set) != 1:
                # The system aren't synced yet.
                break
            if parent_id_set == {camera.parent_id}:
                # Parent isn't changed yet.
                break
            result.append(camera_from_servers_list[0])
        else:
            return result
    #  Parent server hasn't been changed for at least one camera.
    return [got or exp for got, exp in zip_longest(result, cameras)]


def _advertise_to_many(camera_url, servers):
    camera_url = urlparse(camera_url)
    MediaserversDNSSDScope(servers).advertise_once([
        DNSSDWebService('camera', camera_url.hostname, camera_url.port, camera_url.path)])


def _get_camera_for_servers(camera_id, mediaservers):
    cameras = []
    for mediaserver in mediaservers:
        camera = mediaserver.api.get_camera(camera_id)
        if camera is None:
            # Mediaservers aren't synced yet.
            break
        cameras.append(camera)
    return cameras
