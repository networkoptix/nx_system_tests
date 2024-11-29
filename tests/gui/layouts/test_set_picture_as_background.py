# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_set_picture_as_background(VMSTest):
    """Set picture as background.

    Create layout, add picture, set picture as layout background,
    check background is set, check saved default parameters of background.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/933

    Selection-Tag: 933
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        scene_item = ResourceTree(testkit_api, hid).get_local_file('test_background.png').open()
        LayoutTabBar(testkit_api, hid).save_current_as('New Layout 1')
        scene_item.right_click()
        QMenu(testkit_api, hid).activate_items("Set as Layout Background")
        progress_dialog = BaseWindow(api=testkit_api, locator_or_obj={
            "type": "nx::vms::client::desktop::ProgressDialog",
            "unnamed": 1,
            "visible": 1,
            "windowTitle": "Updating Background...",
            })
        progress_dialog.wait_until_closed(10)
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        scene = Scene(testkit_api, hid)
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)
        layout_settings = scene.open_layout_settings()
        layout_settings.open_background_tab()
        assert layout_settings.get_crop_checkbox().is_checked()
        assert layout_settings.get_aspect_ratio_field().is_checked()
        assert layout_settings.get_opacity_field().get_text() == '69%'
        assert layout_settings.get_width_field().get_text() == '5 cells'
        assert layout_settings.get_height_field().get_text() == '5 cells'


if __name__ == '__main__':
    exit(test_set_picture_as_background().main())
