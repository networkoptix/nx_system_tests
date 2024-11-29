# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_save_layout_as(VMSTest):
    """Save Layout As for existing layout.

    Save layout with two items, add 3rd item and save layout as.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/923

    Selection-Tag: 923
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
        ResourceTree(testkit_api, hid).wait_for_any_local_file(timeout=60)
        scene = Scene(testkit_api, hid)
        ResourceTree(testkit_api, hid).select_files(['pic_1.bmp', 'pic_2.bmp']).open_by_context_menu()
        scene.wait_for_items_number(2)
        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.save('New Layout 1*')
        tab_bar.wait_for_open('New Layout 1')
        tab_bar.save_current_as('Test1')
        ResourceTree(testkit_api, hid).get_local_file('pic_0.jpg').open()
        scene.wait_for_items_number(3)
        tab_bar.save_current_as('Test2')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('Test1')
        assert rtree.get_layout('Test1').get_local_file('pic_1.bmp').is_image()
        assert rtree.get_layout('Test1').get_local_file('pic_2.bmp').is_image()
        assert rtree.has_layout('Test2')
        assert rtree.get_layout('Test2').get_local_file('pic_1.bmp').is_image()
        assert rtree.get_layout('Test2').get_local_file('pic_2.bmp').is_image()
        assert rtree.get_layout('Test2').get_local_file('pic_0.jpg').is_image()


if __name__ == '__main__':
    exit(test_save_layout_as().main())
