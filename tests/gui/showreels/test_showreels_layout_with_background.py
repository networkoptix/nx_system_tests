# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.showreels import Showreel
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_showreels_layout_with_background(VMSTest):
    """Showreel custom item rotation or ar.

    Add items with custom AR or rotation to showreel.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16208

    Selection-Tag: 16208
    Selection-Tag: showreels
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
        scene = Scene(testkit_api, hid)
        LayoutTabBar(testkit_api, hid).create('Test Layout')
        layout_settings = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings.set_background(remote_background)
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)

        MainMenu(testkit_api, hid).activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        showreel = Showreel(testkit_api, hid)
        ResourceTree(testkit_api, hid).get_layout('Test Layout').drag_n_drop_at(showreel.get_first_placeholder_coords())

        image = SavedImage(gui_prerequisite_store.fetch('test16208/screen.png'))
        item = showreel.get_item('Test Layout')
        # Both AR and rotation are checked through picture comparison.
        assert item.image_capture().is_similar_to(image)

        showreel.start()
        assert Scene(testkit_api, hid).has_background()
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)


if __name__ == '__main__':
    exit(test_showreels_layout_with_background().main())
