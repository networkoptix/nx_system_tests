# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Collection

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import MediaserverArchive
from mediaserver_api import MediaserverApiV1
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import add_main_storage
from vm.hypervisor import Vm


def make_three_archives(server: Mediaserver, vm_control: Vm) -> Collection[MediaserverArchive]:
    api = server.api
    [default_storage] = api.list_storages(server.default_archive().storage_root_path())
    api.disable_storage(default_storage.id)
    api_storage_one = add_main_storage(server, vm_control, 'P', 20_000)
    api_storage_two = add_main_storage(server, vm_control, 'Q', 20_000)
    api_backup_storage = add_backup_storage(server, vm_control, 'V', 20_000)
    return (
        server.archive(api_storage_one.path),
        server.archive(api_storage_two.path),
        server.archive(api_backup_storage.path),
        )


def _test_backup_from_disabled_main_storage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    [archive_one, archive_two, backup_archive] = make_three_archives(mediaserver, one_mediaserver.vm().vm_control)

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    [recorded_period] = record_from_cameras(api, [camera], camera_server, 30)
    storage_one_archive_size_after = archive_one.camera_archive(camera.physical_id).size_bytes()
    storage_two_archive_size_after = archive_two.camera_archive(camera.physical_id).size_bytes()
    assert storage_one_archive_size_after > 0
    assert storage_two_archive_size_after > 0
    one_camera_archive = archive_one.camera_archive(camera.physical_id)
    two_camera_archive = archive_two.camera_archive(camera.physical_id)
    assert not recorded_period.is_among(one_camera_archive.low().list_periods(), tolerance_sec=0.1)
    assert not recorded_period.is_among(one_camera_archive.high().list_periods(), tolerance_sec=0.1)
    assert not recorded_period.is_among(two_camera_archive.low().list_periods(), tolerance_sec=0.1)
    assert not recorded_period.is_among(two_camera_archive.high().list_periods(), tolerance_sec=0.1)

    [api_storage_one] = api.list_storages(archive_one.storage_root_path())
    assert api_storage_one.is_enabled
    api.disable_storage(api_storage_one.id)
    api_storage_one = api.get_storage(api_storage_one.id)
    assert not api_storage_one.is_enabled

    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera.id)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()

    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    assert recorded_period.is_among(backup_camera_archive.low().list_periods())
    assert recorded_period.is_among(backup_camera_archive.high().list_periods())
