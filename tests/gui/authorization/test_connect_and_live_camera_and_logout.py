# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import ServerSceneItem
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelinePlaceholder
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_connect_and_live_camera_and_logout(VMSTest):
    """Connect to system and check live camera and logout.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6716
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1480

    Selection-Tag: 6716
    Selection-Tag: 1480
    Selection-Tag: authorization
    Selection-Tag: camera_management
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_to_server(testkit_api, hid, address_port, server_vm)
        rtree = ResourceTree(testkit_api, hid)
        server_name = server_vm.api.get_server_name()
        rtree.get_server(server_name).open_monitoring()
        ServerSceneItem(testkit_api, hid, server_name).wait_for_accessible()

        camera_scene_item = rtree.get_camera(test_camera_1.name).open()
        assert camera_scene_item.video_is_playing()
        timeline_placeholder = TimelinePlaceholder(testkit_api)
        assert timeline_placeholder.is_enabled()
        assert timeline_placeholder.get_camera_name() == test_camera_1.name
        assert TimelineControlWidget(testkit_api, hid).live_button.is_checked()


if __name__ == '__main__':
    exit(test_connect_and_live_camera_and_logout().main())
