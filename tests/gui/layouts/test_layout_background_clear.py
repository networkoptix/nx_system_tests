# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_layout_background_clear(VMSTest):
    """Layout can have background set and cleared.

    Background is cleared using layout settings
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/895

    Selection-Tag: 895
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
        scene = Scene(testkit_api, hid)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.create('Test')
        layout_settings = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings.set_background(remote_background)

        rtree = ResourceTree(testkit_api, hid)
        rtree.get_layout('Test').open()
        assert layout_tab_bar.is_open('Test')
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)

        scene.open_layout_settings().clear_background()
        assert layout_tab_bar.is_open('Test')
        assert not scene.has_background()

        layout_tab_bar.save('Test')
        layout_tab_bar.close('Test')
        rtree.get_layout('Test').open()
        assert layout_tab_bar.is_open('Test')
        assert not scene.has_background()


if __name__ == '__main__':
    exit(test_layout_background_clear().main())
