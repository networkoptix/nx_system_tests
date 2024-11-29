# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.select_background_file import BackgroundFileDialog
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_default_background_files(VMSTest):
    """Default background files and default cells value for background.

    Open default background folder, check default background files,
    choose one of them, check default width and height.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/900

    Selection-Tag: 900
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
        layout_settings = Scene(testkit_api, hid).open_layout_settings()
        layout_settings.open_background_tab()
        background_folder = client_installation.os_access.home() / 'Pictures' / 'Nx Witness Backgrounds'
        layout_settings.browse_background_default_folder(background_folder)
        background_file_dialog = BackgroundFileDialog(testkit_api, hid)
        for file in ['Cafe.jpg', 'School.jpg', 'School 2.jpg']:
            assert file in background_file_dialog.filenames()
        background_file_dialog.double_click_file('Cafe.jpg')
        background_file_dialog.wait_until_closed()
        assert layout_settings.get_width_field().get_text() == '30 cells'
        assert layout_settings.get_height_field().get_text() == '52 cells'


if __name__ == '__main__':
    exit(test_default_background_files().main())
