# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_save_configuration_if_client_is_not_connected_to_server(VMSTest):
    """Not able to save configuration if Client is not connected to Server.

    #  https://networkoptix.testrail.net/index.php?/cases/view/79104

    Selection-Tag: 79104
    Selection-Tag: session_restore
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        assert not MainMenu(testkit_api, hid).has_save_window_configuration()


if __name__ == '__main__':
    exit(test_save_configuration_if_client_is_not_connected_to_server().main())
