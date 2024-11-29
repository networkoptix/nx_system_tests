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
    """Test enable failover on one server.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/744
    """

    def _run(self, args, exit_stack):
        _test_enable_failover_on_one_server(args.distrib_url, 'v0', exit_stack)


def _test_enable_failover_on_one_server(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [one, two, three] = exit_stack.enter_context(pool.three_mediaservers({'licenseServer': license_server.url()}))
    configure_license(one, license_server)
    configure_license(two, license_server)
    configure_license(three, license_server)
    one.api.enable_failover(max_cameras=1)
    two.api.enable_failover(max_cameras=2)
    three.api.enable_failover(max_cameras=1)
    cameras = []
    for index, server in enumerate([one, two, three]):
        camera = discover_camera(server, camera_server, f'/test{index}.mjpeg')
        cameras.append(camera)
        server_id = server.api.get_server_id()
        server.api.set_camera_preferred_parent(camera.id, server_id)
    merge_many_servers([one, two, three])
    one.stop()
    [camera, *_] = cameras
    [camera] = advertise_to_change_camera_parent([camera], [two, three])
    assert camera.parent_id == two.api.get_server_id()
    one.start()
    [camera] = advertise_to_change_camera_parent([camera], [one, two, three])
    assert camera.parent_id == one.api.get_server_id()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
