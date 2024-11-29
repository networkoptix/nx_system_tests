# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_low_quality_for_new_added_cameras(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    camera_server = MultiPartJpegCameraServer()
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()

    assert not first.api.backup_is_enabled_for_newly_added_cameras()
    assert not second.api.backup_is_enabled_for_newly_added_cameras()
    first.api.enable_backup_for_newly_added_cameras()
    first.api.set_backup_quality_for_newly_added_cameras(low=True, high=False)

    [camera] = add_cameras(second, camera_server)
    assert second.api.backup_is_enabled_for_newly_added_cameras()
    backup_quality_for_new_added_cameras = second.api.get_backup_quality_for_newly_added_cameras()
    assert backup_quality_for_new_added_cameras.low
    assert not backup_quality_for_new_added_cameras.high

    assert second.api.camera_backup_is_enabled(camera.id)
    camera_backup_quality = second.api.get_camera_backup_quality(camera.id)
    assert camera_backup_quality.low
    assert not camera_backup_quality.high
    [backup_content_type] = camera.backup_type
    assert backup_content_type == 'archive'
