# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.waiting import wait_for_truthy


def _storage_is_writable(api, storage_path):
    [storage] = api.list_storages(storage_path)
    return storage.is_writable


def _test_removable_storage(distrib_url, one_vm_type, before_start, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    os = mediaserver.os_access
    [default] = api.list_storages()

    def plug_in_removable_storage():
        one_mediaserver.hardware().add_disk('usb', 15 * 1000)
        return os.mount_disk('Q')

    if before_start:
        mediaserver.stop()
        new_disk_path = plug_in_removable_storage()
        mediaserver.start()
    else:
        new_disk_path = plug_in_removable_storage()
    discovered_storage, new_storage = api.set_up_new_storage(new_disk_path)
    assert not discovered_storage.is_enabled
    storage_type_renamed = api.specific_features().get('partition_type_usb_renamed_to_removable')
    expected_storage_type = 'removable' if storage_type_renamed == 1 else 'usb'
    assert new_storage.type == expected_storage_type
    api.disable_storage(default.id)
    [camera] = add_cameras(mediaserver, camera_server)
    [period] = record_from_cameras(api, [camera], camera_server, 10)
    assert 5 <= period.duration_sec <= 15
    mediaserver.stop()
    mediaserver.start()
    usb_archive = mediaserver.archive(new_storage.path)
    usb_camera_archive = usb_archive.camera_archive(camera.physical_id)
    [period_from_filename] = usb_camera_archive.high().list_periods()
    assert period_from_filename == period
    # It's very rare, but storage can appear not writable for a few moments.
    wait_for_truthy(_storage_is_writable, args=[api, str(new_disk_path)])
    [new_period] = record_from_cameras(api, [camera], camera_server, 10)
    assert new_period.is_among(usb_camera_archive.high().list_periods())
