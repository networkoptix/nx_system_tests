# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.cameras_and_storages.archive_rewrite.common import _fill_storage_with_other_data
from tests.cameras_and_storages.archive_rewrite.common import _prepare_archive
from tests.cameras_and_storages.archive_rewrite.common import add_two_archives
from tests.cameras_and_storages.archive_rewrite.common import configure_mediaserver
from tests.waiting import wait_for_truthy


def _test_archive_rewrite_with_one_storage_disabled(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    os = one_mediaserver.os_access()
    api = one_mediaserver.api()
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    configure_mediaserver(license_server, mediaserver)
    video_source = JPEGSequence(frame_size=(3840, 2160))
    camera_server = MultiPartJpegCameraServer(video_source=video_source)
    [camera] = add_cameras(mediaserver, camera_server)
    api.start_recording(camera.id)
    first_archive, second_archive = add_two_archives(
        mediaserver, one_mediaserver.hardware())
    [_, second_period_before] = _prepare_archive(
        api,
        first_archive,
        second_archive,
        camera,
        )
    first_storage_path = first_archive.storage_root_path()
    second_storage_path = second_archive.storage_root_path()
    [first] = api.list_storages(first_storage_path)
    [second] = api.list_storages(second_storage_path)
    _fill_storage_with_other_data(os, second)
    api.disable_storage(first.id)
    camera_server.serve(time_limit_sec=10)
    wait_for_truthy(
        _storage_cleared, args=[first_archive.camera_archive(camera.physical_id)])
    second_camera_archive = second_archive.camera_archive(camera.physical_id)
    [second_period_after, _] = second_camera_archive.high().list_periods()
    assert second_period_after.start > second_period_before.start


def _storage_cleared(camera_archive):
    periods_low = camera_archive.low().list_periods()
    periods_high = camera_archive.high().list_periods()
    return not (periods_low or periods_high)
