# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.scene_items import SceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_dewarping_in_local_files(VMSTest):
    """360 dewarping in Local Files mode for no server.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78384

    Selection-Tag: 78384
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
        localfile_node.open()
        with localfile_node.open_settings() as file_settings:
            file_settings.enable_dewarping()
            file_settings.set_equirectangular_dewarping_mode()
        loaded_dewarped = SavedImage(gui_prerequisite_store.fetch('test78384/dewarped.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded_dewarped)
        item = SceneItem(testkit_api, hid, 'camera_no_watermark.png')
        assert item.has_button('Dewarping')

        item.click_button('Dewarping')
        loaded = SavedImage(gui_prerequisite_store.fetch('comparison/camera_no_watermark.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        item.click_button('Dewarping')
        scene.wait_until_first_item_is_similar_to(loaded_dewarped)


if __name__ == '__main__':
    exit(test_dewarping_in_local_files().main())
