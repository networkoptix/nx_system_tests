# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_add_camera_during_rebuild_archive(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    camera_server = MultiPartJpegCameraServer()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    audit_trail = mediaserver.api.audit_trail()
    [camera] = add_cameras(mediaserver, camera_server)
    record_from_cameras(mediaserver.api, [camera], camera_server, 5)
    history = [mediaserver.api.get_server_id()]
    assert mediaserver.api.get_camera_history(camera.id) == history
    [camera_insert_record, *_] = audit_trail.wait_for_sequence()
    assert camera_insert_record.type == mediaserver.api.audit_trail_events.CAMERA_INSERT
    assert camera_insert_record.resources == [camera.id]
    camera_archive = mediaserver.default_archive().camera_archive(camera.physical_id)
    assert camera_archive.low().has_info()
    assert camera_archive.high().has_info()
    mediaserver.api.set_system_settings({'autoDiscoveryEnabled': 'false'})
    mediaserver.api.remove_resource(camera.id)
    mediaserver.api.rebuild_main_archive()
    assert mediaserver.api.get_camera_history(camera.id) == history
    records = audit_trail.wait_for_sequence()
    assert mediaserver.api.audit_trail_events.CAMERA_INSERT not in [record.type for record in records]
