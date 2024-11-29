# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

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


class test_horizon_correction_image(VMSTest):
    """Horizon correction Image.

    360 VR dewarping --> Horizon correction Image

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78223

    Selection-Tag: 78223
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('test78223/dewarping.jpg', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        localfile_node = ResourceTree(testkit_api, hid).get_local_file('dewarping.jpg')
        item = localfile_node.open()
        with localfile_node.open_settings() as file_settings:
            file_settings.enable_dewarping()
            file_settings.set_equirectangular_dewarping_mode()
            assert file_settings.are_horizontal_options_accessible()

            file_settings.set_alfa(71.3)
            file_settings.set_beta(-24.4)
            path = gui_prerequisite_store.fetch('test78223/correction_preview_set.jpg')
            preview = file_settings.get_dewarping_preview_equirectangular()
            assert preview.is_similar_to(SavedImage(path))
        # Time for rendering of new settings.
        time.sleep(1)
        item.hover()
        item.set_dewarping('360')
        scene = Scene(testkit_api, hid)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78223/correction_set.jpg'))
        scene.wait_until_first_item_is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.reset_settings()
            path = gui_prerequisite_store.fetch('test78223/correction_preview_reset.jpg')
            preview = file_settings.get_dewarping_preview_equirectangular()
            assert preview.is_similar_to(SavedImage(path))
            assert abs(file_settings.get_alfa() - 0.0) < 1e-6
            assert abs(file_settings.get_beta() - 0.0) < 1e-6
        # Time for rendering of new settings.
        time.sleep(1)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78223/correction_reset.jpg'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_horizon_correction_image().main())
