# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_info_enhancement(VMSTest):
    """Info and Image Enhancement and change layouts.

    Activate "Image Enhancement" and "Information" buttons for an item at the first layout,
    switch on to the second layout and back to the first layout,
    check these buttons are still activated.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/938

    Selection-Tag: 938
    Selection-Tag: layouts
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        server_vm.api.start_recording(test_camera_1.id, test_camera_2.id)
        testkit_api, camera_1_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name, layout_name='Layout1')
        hid = HID(testkit_api)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save('Layout1')
        ResourceTree(testkit_api, hid).get_camera(test_camera_2.name).open()
        layout_tab_bar.save_current_as('Layout2')
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_layout('Layout1').open()
        with camera_1_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_image_enhancement(True)
        camera_1_scene_item.activate_button('Information')
        rtree.get_layout('Layout2').open()
        rtree.get_layout('Layout1').open()
        with camera_1_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            assert image_enhancement_dialog.get_image_enhancement()
        assert camera_1_scene_item.button_checked('Information')


if __name__ == '__main__':
    exit(test_info_enhancement().main())
