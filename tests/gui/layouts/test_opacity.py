# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_opacity(VMSTest):
    """Opacity.

    Set background for a layout, open layout in new tab,
    set opacity as 5 for the background, compare with expected picture,
    set opacity as 100 for the background, compare with expected picture.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/896

    Selection-Tag: 896
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
        layout_settings_1 = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings_1.set_background(remote_background)
        ResourceTree(testkit_api, hid).get_layout('New Layout 1').open_in_new_tab()
        layout_settings_2 = scene.open_layout_settings()
        layout_settings_2.open_background_tab()
        layout_settings_2.get_opacity_field().type_text('5')
        layout_settings_2.save_settings()
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)
        layout_settings_3 = scene.open_layout_settings()
        layout_settings_3.open_background_tab()
        layout_settings_3.get_opacity_field().type_text('100')
        layout_settings_3.save_settings()
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)


if __name__ == '__main__':
    exit(test_opacity().main())
