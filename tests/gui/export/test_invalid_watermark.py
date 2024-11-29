# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_invalid_watermark(VMSTest):
    """Invalid watermark.

    Open file with invalid watermark, check its watermark

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20889

    Selection-Tag: 20889
    Selection-Tag: export
    Selection-Tag: watermarks_export
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('test20889/invalid_watermark.mkv', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        scene_item = ResourceTree(testkit_api, hid).get_local_file('invalid_watermark.mkv').open_in_new_tab()
        scene_item.wait_for_accessible()
        with scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_not_matched()


if __name__ == '__main__':
    exit(test_invalid_watermark().main())
