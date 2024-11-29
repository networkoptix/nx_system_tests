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
    """Test enable failover on two servers.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/46950
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57207
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57215
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57232
    """

    def _run(self, args, exit_stack):
        _test_enable_failover_on_two_servers(args.distrib_url, 'v0', exit_stack)


def _test_enable_failover_on_two_servers(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [one, two, three] = exit_stack.enter_context(pool.three_mediaservers({'licenseServer': license_server.url()}))
    configure_license(one, license_server)
    configure_license(two, license_server)
    configure_license(three, license_server)
    one.api.enable_failover(max_cameras=2)
    two.api.enable_failover(max_cameras=2)
    cameras = []
    for index, server in enumerate([one, two, two, three]):
        camera = discover_camera(server, camera_server, f'/test{index}.mjpeg')
        cameras.append(camera)
        server_id = server.api.get_server_id()
        server.api.set_camera_preferred_parent(camera.id, server_id)
    [_, camera_2_1, camera_2_2, _] = cameras
    merge_many_servers([one, two, three])
    # Make sure that third mediaserver has received information about all cameras in the system.
    # Otherwise, it won't be able to distinguish discovered camera from the existing ones,
    # which means it won't be able to find out that this camera belongs to another mediaserver
    three.api.wait_for_cameras_synced([one.api, two.api])
    two.stop()
    [camera_2_1] = advertise_to_change_camera_parent([camera_2_1], [one, three])
    assert camera_2_1.parent_id == one.api.get_server_id()
    three.api.enable_failover(max_cameras=2)
    [camera_2_2] = advertise_to_change_camera_parent([camera_2_2], [three, one])
    assert camera_2_2.parent_id == three.api.get_server_id()
    two.start()
    [camera_2_1, camera_2_2] = advertise_to_change_camera_parent(
        [camera_2_1, camera_2_2], [one, two, three])
    assert camera_2_1.parent_id == two.api.get_server_id()
    assert camera_2_2.parent_id == two.api.get_server_id()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
