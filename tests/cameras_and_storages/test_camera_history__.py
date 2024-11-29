# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras

_logger = logging.getLogger(__name__)


def _test_camera_switching_should_be_represented_in_history(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.api.set_license_server(license_server.url())
    one.allow_license_server_access(license_server.url())
    brand = one.api.get_brand()
    key = license_server.generate({'BRAND2': brand})
    one.api.activate_license(key)
    [camera] = add_cameras(one, camera_server)
    # After camera is moved, synchronization shouldn't take long.
    # History update takes a while. History synchronization does not.
    record_from_cameras(one.api, [camera], camera_server, 5)
    history = [one.api.get_server_id()]
    assert one.api.get_camera_history(camera.id) == history
    assert two.api.get_camera_history(camera.id) == history
    _logger.info("Switch camera to `two`.")
    two.api.set_camera_parent(camera.id, two.api.get_server_id())
    record_from_cameras(one.api, [camera], camera_server, 5)
    history.append(two.api.get_server_id())
    assert one.api.get_camera_history(camera.id) == history
    assert two.api.get_camera_history(camera.id) == history
    _logger.info("Switch camera back to `one`.")
    one.api.set_camera_parent(camera.id, one.api.get_server_id())
    record_from_cameras(one.api, [camera], camera_server, 5)
    history.append(one.api.get_server_id())
    assert one.api.get_camera_history(camera.id) == history
    assert two.api.get_camera_history(camera.id) == history
