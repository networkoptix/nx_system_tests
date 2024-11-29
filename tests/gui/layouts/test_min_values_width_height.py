# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_min_values_width_height(VMSTest):
    """Min value for Width and Height.

    Set background, check "Crop" setting is not checked,
    set value of "Width" as 5, check value of "Height" is changed also,
    check 5 is minimum value of "Width", set checkbox "Crop",
    check new corresponding values of "Width" and "Height",
    set value of "Height" as 5, check 5 is minimum value of "Height".
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/899

    Selection-Tag: 899
    Selection-Tag: layouts
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
        scene = Scene(testkit_api, hid)
        layout_settings_1 = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/cat42.jpg', client_installation.os_access)
        layout_settings_1.set_background(remote_background)
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/cat42.jpg'))
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)
        layout_settings_2 = scene.open_layout_settings()
        layout_settings_2.open_background_tab()
        assert not layout_settings_2.get_crop_checkbox().is_checked()
        layout_settings_2.get_width_field().type_text('0')
        # This click is needed to change the focus from field to get the default minimum value
        layout_settings_2.get_height_field().click()
        minimum_width = layout_settings_2.get_width_field().get_text()
        assert minimum_width == '5 cells'


if __name__ == '__main__':
    exit(test_min_values_width_height().main())
