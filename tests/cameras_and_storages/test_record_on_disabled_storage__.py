# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_record_on_disabled_storage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    [camera] = add_cameras(mediaserver, camera_server)
    mediaserver.api.set_license_server(license_server.url())
    mediaserver.allow_license_server_access(license_server.url())
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand})
    mediaserver.api.activate_license(key)
    api.start_recording(camera.id)
    storages = api.list_storages()
    for storage in storages:
        api.disable_storage(storage.id)
    for storage in api.list_storages():
        assert not storage.is_enabled
    camera_server.serve(time_limit_sec=5)
    [periods] = api.list_recorded_periods([camera.id])
    assert not periods
