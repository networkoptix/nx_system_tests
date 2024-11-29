# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.showreels import Showreel
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_rename_showreels(VMSTest):
    """Rename showreel by right click and hotkey.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16199

    Selection-Tag: 16199
    Selection-Tag: showreels
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        MainMenu(testkit_api, hid).activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        rtree = ResourceTree(testkit_api, hid)
        showreel = rtree.get_showreel('Showreel').open()
        rtree.get_camera(test_camera_1.name).drag_n_drop_at(showreel.get_first_placeholder_coords())
        rtree.get_showreel('Showreel').rename_using_context_menu('test showreel')
        assert Showreel(testkit_api, hid).get_showreel_name() == 'test showreel'

        ResourceTree(testkit_api, hid).get_showreel('test showreel').rename_using_hotkey('test showreel another')
        assert Showreel(testkit_api, hid).get_showreel_name() == 'test showreel another'


if __name__ == '__main__':
    exit(test_rename_showreels().main())
