# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket
import time

from directories import get_run_dir
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.audit_trail import AuditTrail
from gui.desktop_ui.audit_trail import AuditTrailCamerasTable
from gui.desktop_ui.audit_trail import AuditTrailDetailsTable
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_check_search_in_audit_trail(VMSTest):
    """Check Search in Audit trail.

    Open Audit Trail dialog, input name of camera or IP in search panel. Check result.

    #  https://networkoptix.testrail.net/index.php?/cases/view/2110

    Selection-Tag: 2110
    Selection-Tag: audit_trail
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        rtsp_server = MjpegRtspCameraServer()
        [rtsp1] = add_cameras(server_vm, rtsp_server, indices=[0])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        exit_stack.enter_context(rtsp_server.async_serve())
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, video_file))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm, video_file=video_file)
        ResourceTree(testkit_api, hid).wait_for_cameras([rtsp1.name, test_camera_1.name])
        audit_trail = AuditTrail.open(testkit_api, hid)
        audit_trail.set_tab('Cameras')
        time.sleep(.5)
        audit_trail.search(test_camera_1.name)
        time.sleep(.5)
        camera = AuditTrailCamerasTable(testkit_api, hid).get_camera(test_camera_1.name)
        assert camera.ip == socket.gethostbyname(test_camera_1.address)
        audit_trail.set_tab('Cameras')
        assert AuditTrailCamerasTable(testkit_api, hid).count_rows() == 1

        audit_trail.search('127.0.0.100')
        time.sleep(.5)
        camera1 = AuditTrailCamerasTable(testkit_api, hid).get_camera(test_camera_1.name)
        assert camera1.ip == socket.gethostbyname(test_camera_1.address)
        audit_trail.set_tab('Cameras')
        assert AuditTrailCamerasTable(testkit_api, hid).count_rows() == 1

        audit_trail.search('after 42')
        time.sleep(.5)
        assert AuditTrailCamerasTable(testkit_api, hid).is_empty()
        assert AuditTrailDetailsTable(testkit_api, hid).is_empty()
        audit_trail.close()
        time.sleep(1)


if __name__ == '__main__':
    exit(test_check_search_in_audit_trail().main())
