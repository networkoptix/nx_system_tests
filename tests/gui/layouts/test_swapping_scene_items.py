# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import SceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_swapping_scene_items(VMSTest):
    """Swapping scene items.

    Add 3 items to a layout, swap 2 of them, the other item should stay unaltered.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1177

    Selection-Tag: 1177
    Selection-Tag: layouts
    Selection-Tag: scene_items
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        uploaded = []
        uploaded.append(gui_prerequisite_supplier.upload_to_remote('localfiles/pic_1.bmp', client_installation.os_access))
        uploaded.append(gui_prerequisite_supplier.upload_to_remote('localfiles/pic_2.bmp', client_installation.os_access))
        uploaded.append(gui_prerequisite_supplier.upload_to_remote('localfiles/pic_0.jpg', client_installation.os_access))
        [remote_path] = {p.parent for p in uploaded}
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        rtree = ResourceTree(testkit_api, hid)
        rtree.select_files(['pic_1.bmp', 'pic_2.bmp', 'pic_0.jpg']).open_by_context_menu()
        # Check if the latest open resource is shown on the scene
        scene_item_0 = SceneItem(testkit_api, hid, 'pic_0.jpg')
        scene_item_0.wait_for_accessible()
        scene_item_1 = SceneItem(testkit_api, hid, 'pic_1.bmp')
        scene_item_2 = SceneItem(testkit_api, hid, 'pic_2.bmp')
        pic2_bounds_before = scene_item_2.bounds()
        scene_item1_center = scene_item_1.center()
        scene_item2_center = scene_item_0.center()
        hid.mouse_drag_and_drop(scene_item_1.center(), scene_item_0.center())
        time.sleep(2.5)
        center2 = scene_item_0.center()
        center1 = scene_item_1.center()
        assert scene_item1_center.chessboard_distance(center2) < 5, (
            "The first item is located incorrectly")
        assert scene_item2_center.chessboard_distance(center1) < 5, (
            "The second item is located incorrectly")
        assert scene_item_2.bounds().displacement_from(pic2_bounds_before) < 5
        original_image = SavedImage(gui_prerequisite_store.fetch('localfiles//pic_2.bmp'))
        screen = scene_item_2.image_capture().crop_border(1)
        assert screen.is_similar_to(original_image.get_grayscale())


if __name__ == '__main__':
    exit(test_swapping_scene_items().main())
