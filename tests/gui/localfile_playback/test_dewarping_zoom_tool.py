# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_dewarping_zoom_tool(VMSTest):
    """Zoom tool.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78242

    Selection-Tag: 78242
    Selection-Tag: localfile_playback
    Selection-Tag: dewarping
    Selection-Tag: gui-smoke-test
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('localfiles/camera_no_watermark.png', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        localfile_node = ResourceTree(testkit_api, hid).get_local_file('camera_no_watermark.png')
        item = localfile_node.open()
        with localfile_node.open_settings() as file_settings:
            file_settings.enable_dewarping()
            file_settings.set_equirectangular_dewarping_mode()
        loaded = SavedImage(gui_prerequisite_store.fetch('test78242/dewarped1.png'))
        scene = Scene(testkit_api, hid)
        assert scene.item_image(0).is_similar_to(loaded)
        assert item.has_button('Dewarping')

        item.create_zoom_window()
        loaded = SavedImage(gui_prerequisite_store.fetch('test78242/dewarped2.png'))
        assert scene.item_image(1).is_similar_to(loaded)

        bounds = item.border_of_zoom().bounds()
        hid.mouse_drag_and_drop(
            bounds.center(),
            bounds.center().right(bounds.width).left(1).down(bounds.height).up(1),
            )
        loaded = SavedImage(gui_prerequisite_store.fetch('test78242/dewarped3.png'))
        assert scene.item_image(1).is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_dewarping_zoom_tool().main())
