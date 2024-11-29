# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_showreels_navigation_by_keys(VMSTest):
    """Showreels navigation by keys.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16186

    Selection-Tag: 16186
    Selection-Tag: showreels
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        test_http_server = create_test_http_server('dropdown_page')
        exit_stack.enter_context(test_http_server)
        link = f'http://{client_installation.os_access.source_address()}:{test_http_server.server_port}'
        server_vm.api.add_web_page('Dropdown', link)
        server_vm.api.add_web_page('TestPage', link)
        server_vm.api.add_web_page('TestPage1', link)
        server_vm.api.add_web_page('TestPage2', link)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        MainMenu(testkit_api, hid).activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        rtree = ResourceTree(testkit_api, hid)
        showreel = rtree.get_showreel('Showreel').open()
        rtree.get_webpage('TestPage').drag_n_drop_at(showreel.get_first_placeholder_coords())
        rtree.get_webpage('TestPage1').drag_n_drop_at(showreel.get_first_placeholder_coords())
        rtree.get_webpage('TestPage2').drag_n_drop_at(showreel.get_first_placeholder_coords())
        showreel.get_item('TestPage').set_display_time(99)
        showreel.get_item('TestPage1').set_display_time(99)
        showreel.get_item('TestPage2').set_display_time(99)
        showreel.start()
        scene_item_1 = WebPageSceneItem(testkit_api, hid, 'TestPage')
        scene_item_1.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Right')
        scene_item_2 = WebPageSceneItem(testkit_api, hid, 'TestPage1')
        scene_item_2.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Down')
        scene_item_3 = WebPageSceneItem(testkit_api, hid, 'TestPage2')
        scene_item_3.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('PgDown')
        scene_item_1.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Enter')
        scene_item_2.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Space')
        scene_item_3.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Left')
        scene_item_2.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Up')
        scene_item_1.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('PgUp')
        scene_item_3.wait_for_accessible(0.1)

        hid.keyboard_hotkeys('Backspace')
        scene_item_2.wait_for_accessible(0.1)


if __name__ == '__main__':
    exit(test_showreels_navigation_by_keys().main())
