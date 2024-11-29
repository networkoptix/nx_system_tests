# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV1
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from mediaserver_scenarios.storage_preparation import create_smb_share


def _test_limit_bandwidth(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    user = 'UserWithPassword'
    password = 'GoodPassword'
    server = mediaserver_unit.installation()
    api: MediaserverApiV1 = server.api
    # Set minimal sample duration to make this test faster.
    server.update_conf({'mediaFileDuration': 1})
    server.allow_license_server_access(license_server.url())
    server.start()
    api.setup_local_system({'licenseServer': license_server.url()})
    brand = api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    api.activate_license(key)
    # Since shares are reused in tests and Windows doesn't delete SMB connections,
    # it's necessary to use different SMB shares for positive and negative tests.
    [share_name, smb_share_path] = create_smb_share(smb_machine.os_access, user, password, 300 * 1024**3, 'P')
    smb_storage = server.archive_on_remote(smb_machine.os_access, smb_share_path)

    api.add_smb_storage(smb_address, share_name, user, password, is_backup=True)

    [camera] = add_cameras(server, camera_server)
    api.enable_secondary_stream(camera.id)
    record_from_cameras(api, [camera], camera_server, 30)

    bandwidth_limit_bps = 1000**2 // 8
    api.limit_backup_bandwidth(bytes_per_sec=bandwidth_limit_bps)
    api.enable_backup_for_cameras([camera.id])

    # Wait for stabilization of backup speed
    stabilization_period_sec = 10
    time.sleep(stabilization_period_sec)

    initial_backup_archive_size = smb_storage.camera_archive(camera.physical_id).size_bytes()
    backup_working_period_sec = 45
    # Wait for some amount of data to be backed up
    time.sleep(backup_working_period_sec)
    updated_backup_archive_size = smb_storage.camera_archive(camera.physical_id).size_bytes()
    assert initial_backup_archive_size < updated_backup_archive_size

    main_archive_size = server.default_archive().camera_archive(camera.physical_id).size_bytes()
    assert updated_backup_archive_size < main_archive_size

    backup_archive_size_diff = updated_backup_archive_size - initial_backup_archive_size
    actual_bandwidth_bps = backup_archive_size_diff / backup_working_period_sec
    assert math.isclose(actual_bandwidth_bps, bandwidth_limit_bps, rel_tol=0.1)
