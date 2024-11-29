# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_many_servers
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.merged_systems.failover.conftest import advertise_to_change_camera_parent
from tests.merged_systems.failover.conftest import configure_license
from tests.merged_systems.failover.conftest import discover_camera


class test_v0(VMSTest):
    """Test camera priorities.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/749
    """

    def _run(self, args, exit_stack):
        _test_camera_priorities(args.distrib_url, 'v0', exit_stack)


def _test_camera_priorities(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [one, two, three] = exit_stack.enter_context(pool.three_mediaservers({'licenseServer': license_server.url()}))
    configure_license(one, license_server)
    configure_license(two, license_server)
    configure_license(three, license_server)
    priorities = ['High', 'Medium', 'Low']
    one_cameras = []
    [one_guid, two_guid, three_guid] = [
        server.api.get_server_id() for server in [one, two, three]]
    for priority in priorities:
        camera = discover_camera(one, camera_server, f'/test_{priority}.mjpeg')
        one_cameras.append(camera)
        one.api.set_camera_preferred_parent(camera.id, one_guid)
        one.api.set_camera_failover_priority(camera.id, priority)
    discover_camera(two, camera_server, '/test_2_1.mjpeg')
    merge_many_servers([one, two, three])
    [camera_high, camera_medium, camera_low] = one_cameras
    one.stop()
    two.api.enable_failover(max_cameras=2)
    [camera_high] = advertise_to_change_camera_parent(
        [camera_high], [two, three], advertising_cameras=one_cameras)
    assert camera_high.parent_id == two_guid
    three.api.enable_failover(max_cameras=1)
    [camera_medium] = advertise_to_change_camera_parent(
        [camera_medium], [two, three], advertising_cameras=one_cameras)
    assert camera_medium.parent_id == three_guid
    three.api.enable_failover(max_cameras=2)
    [camera_low] = advertise_to_change_camera_parent(
        [camera_low], [two, three], advertising_cameras=one_cameras)
    assert camera_low.parent_id == three_guid
    one.start()
    [camera_high, camera_medium, camera_low] = advertise_to_change_camera_parent(
        [camera_high, camera_medium, camera_low], [one, two, three])
    assert camera_high.parent_id == one_guid
    assert camera_medium.parent_id == one_guid
    assert camera_low.parent_id == one_guid


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
