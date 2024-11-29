# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_log_in_as_power_user(VMSTest):
    """Log in as power user.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/121087

    Selection-Tag: 121087
    Selection-Tag: user_access_rights
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        # Administrator|Administrators|Power Users group id.
        group_id = '00000000-0000-0000-0000-100000000001'
        power_user = server_vm.api.add_local_admin('root', 'WellKnownPassword2')
        [address, port] = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)

        connect_to_server_dialog = MainMenu(testkit_api, hid).activate_connect_to_server()
        connect_to_server_dialog.connect(address, power_user.name, '123456', port)
        message_box = MessageBox(testkit_api, hid)
        message_box.wait_until_has_label('Incorrect username or password.')
        message_box.close_by_button('OK')

        connect_to_server_dialog.connect(address, power_user.name, power_user.password, port)
        current_user = ResourceTree(testkit_api, hid).get_current_user()
        assert current_user.name == power_user.name
        settings_general_tab = current_user.open_user_settings().select_general_tab()
        assert current_user.name == settings_general_tab.get_login()
        group_name = server_vm.api.get_group_name(group_id)
        assert group_name == settings_general_tab.get_group()


if __name__ == '__main__':
    exit(test_log_in_as_power_user().main())
