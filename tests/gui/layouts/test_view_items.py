# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.scene_items import SceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_view_items(VMSTest):
    """View items on layout with background.

    Set background, add three items, allocate two items in opposite corners,
    click at each of them one by one, check each item has been increased.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/930

    Selection-Tag: 930
    Selection-Tag: layouts
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
        scene = Scene(testkit_api, hid)
        layout_settings = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings.set_background(remote_background)
        ResourceTree(testkit_api, hid).select_files(['pic_1.bmp', 'pic_2.bmp', 'pic_0.jpg']).open_by_context_menu()
        scene.wait_for_items_number(3)
        scene_item_1 = SceneItem(testkit_api, hid, 'pic_1.bmp')
        scene_item_2 = SceneItem(testkit_api, hid, 'pic_2.bmp')
        scene_item_0 = SceneItem(testkit_api, hid, 'pic_0.jpg')
        scene_item_1.move('-300', '-300')
        scene_item_2.move('300', '300')
        _check_item_can_be_increased(scene_item_1)
        _check_item_can_be_increased(scene_item_2)
        _check_item_can_be_increased(scene_item_0)


def _check_item_can_be_increased(item: SceneItem):
    bounds_before = item.bounds()
    item.click()
    started_at = time.monotonic()
    while True:
        bounds_after = item.bounds()
        if bounds_before.width < bounds_after.width and bounds_before.height < bounds_after.height:
            break
        if time.monotonic() - started_at > 3:
            raise RuntimeError(f'{item} not expanded by click in a timeout!')
        time.sleep(.5)
    item.click()  # back to initial state


if __name__ == '__main__':
    exit(test_view_items().main())
