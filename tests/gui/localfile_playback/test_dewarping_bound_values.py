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


class test_dewarping_bound_values(VMSTest):
    """Boundary values.

    Playing back Local Files > 360 VR dewarping

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78225

    Selection-Tag: 78225
    Selection-Tag: localfile_playback
    Selection-Tag: dewarping
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('test78225/dewarping_horizon.jpeg', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        localfile_node = ResourceTree(testkit_api, hid).get_local_file('dewarping_horizon.jpeg')
        with localfile_node.open_settings() as file_settings:
            file_settings.enable_dewarping()
            file_settings.set_equirectangular_dewarping_mode()
            file_settings.set_alfa(0.0)
            file_settings.set_beta(0.0)
            path = gui_prerequisite_store.fetch('test78225/preview_0_0.png')
            loaded1 = SavedImage(path)
            preview = file_settings.get_dewarping_preview_horizon()
            assert preview.is_similar_to(loaded1)
        item = localfile_node.open()
        item.activate_button('Dewarping')
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_0_0.png'))
        scene = Scene(testkit_api, hid)
        assert scene.first_item_image().is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.set_alfa(180.0)
            file_settings.set_beta(0.0)
            loaded = SavedImage(gui_prerequisite_store.fetch('test78225/preview_180_0.png'))
            preview = file_settings.get_dewarping_preview_horizon()
            assert preview.is_similar_to(loaded)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_180_0.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.set_alfa(-180.0)
            file_settings.set_beta(0.0)
            path2 = gui_prerequisite_store.fetch('test78225/preview_-180_0.png')
            loaded3 = SavedImage(path2)
            preview2 = file_settings.get_dewarping_preview_horizon()
            assert preview2.is_similar_to(loaded3)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_-180_0.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.set_alfa(0.0)
            file_settings.set_beta(90.0)
            loaded = SavedImage(gui_prerequisite_store.fetch('test78225/preview_0_90.png'))
            preview = file_settings.get_dewarping_preview_horizon()
            assert preview.is_similar_to(loaded)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_0_90.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.set_alfa(0.0)
            file_settings.set_beta(-90.0)
            loaded = SavedImage(gui_prerequisite_store.fetch('test78225/preview_0_-90.png'))
            preview = file_settings.get_dewarping_preview_horizon()
            assert preview.is_similar_to(loaded)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_0_-90.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        with localfile_node.open_settings() as file_settings:
            file_settings.set_alfa(90.0)
            file_settings.set_beta(45.0)
            loaded = SavedImage(gui_prerequisite_store.fetch('test78225/preview_90_45.png'))
            preview = file_settings.get_dewarping_preview_horizon()
            assert preview.is_similar_to(loaded)
        loaded = SavedImage(gui_prerequisite_store.fetch('test78225/item_90_45.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_dewarping_bound_values().main())
