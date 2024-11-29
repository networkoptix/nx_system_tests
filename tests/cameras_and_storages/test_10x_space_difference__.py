# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from mediaserver_scenarios.storage_preparation import create_smb_share


def _test_10x_space_difference(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    mediaserver.api.activate_license(key)
    user = 'UserWithPassword'
    password = 'GoodPassword'
    # Since shares are reused in tests and Windows doesn't delete SMB connections,
    # it's necessary to use different SMB shares for positive and negative tests.
    [share_name, _] = create_smb_share(smb_machine.os_access, user, password, int(1.5 * 1024**4), 'P')
    os = mediaserver.os_access
    api = mediaserver.api
    # Set minimal sample duration to make this test faster.
    mediaserver.update_conf({'mediaFileDuration': 1})
    small_disk_size = 11 * 1024 ** 3
    small_path = os.mount_fake_disk('S', small_disk_size)
    large_path = os.mount_fake_disk('L', 11 * small_disk_size)
    mediaserver.stop()
    mediaserver.start()
    [small] = api.list_storages(str(small_path))
    [large] = api.list_storages(str(large_path))
    assert not small.is_writable
    assert large.is_writable
    api.enable_storage(small.id)
    [small] = api.list_storages(str(small_path))
    assert small.is_enabled
    small_free_space_before = small.free_space
    [camera] = add_cameras(mediaserver, camera_server)
    # If small_disk is actually used for writing archive, than we need to record
    # at least 11*mediaFileDuration to see data on it. If use minimal mediaFileDuration,
    # 30 seconds must be enough.
    record_from_cameras(api, [camera], camera_server, duration_sec=30)
    [small] = api.list_storages(str(small_path))
    small_free_space_after = small.free_space
    assert math.isclose(small_free_space_before, small_free_space_after, abs_tol=50000)
    api.add_smb_storage(smb_address, share_name, user, password)
    [small] = api.list_storages(str(small_path))
    [large] = api.list_storages(str(large_path))
    assert not small.is_writable
    assert not large.is_writable
    [period_after] = record_from_cameras(api, [camera], camera_server, duration_sec=10)
    small_archive = mediaserver.archive(small.path)
    large_archive = mediaserver.archive(large.path)
    small_camera_archive = small_archive.camera_archive(camera.physical_id)
    large_camera_archive = large_archive.camera_archive(camera.physical_id)
    assert not small_camera_archive.low().list_periods()
    assert not small_camera_archive.high().list_periods()
    assert not large_camera_archive.low().list_periods()
    assert not period_after.is_among(large_camera_archive.high().list_periods())
