# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.gui_test_stand import GuiTestStand
from gui.mobile_ui.app_window import ApplicationWindow
from gui.mobile_ui.connect_to_server import ConnectToServer
from gui.mobile_ui.scene import Scene
from gui.mobile_ui.warning_dialog import WarningDialog
from gui.mobile_ui.welcome_screen import WelcomeScreen
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_connect_to_system_with_specific_data(VMSTest):
    """Test connect to system with specific data: Case sensitivity, uncommon symbols, etc.

    Selection-Tag: 6601
    Selection-Tag: mobile-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6601
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6600

    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        installer_supplier.distrib().assert_not_older_than('vms_6.1', "Mobile tests only supported by VMS 6.1 and newer")
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        server_vm = exit_stack.enter_context(machine_pool.setup_one_server())
        mobile_client_installation = exit_stack.enter_context(machine_pool.prepared_mobile_client())
        [testkit_api, hid] = mobile_client_installation.start()
        user_1 = server_vm.api.add_local_admin('!#$%^&*_-+=', 'WellKnownPassword2')
        user_2 = server_vm.api.add_local_admin('user', 'qwe!@#$%^&*_-+=')

        # https://networkoptix.testrail.net/index.php?/cases/view/6601
        [server_ip, server_port] = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=user_1.name,
            password=user_1.password,
            )
        WarningDialog(testkit_api, hid).click_button('Connect')
        Scene(testkit_api, hid).wait_for_accessible()
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()

        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=user_2.name,
            password=user_2.password,
            )
        Scene(testkit_api, hid).wait_for_accessible()
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()

        # Username should be case-insensitive.
        # https://networkoptix.testrail.net/index.php?/cases/view/6600
        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=user_2.name.upper(),
            password=user_2.password,
            )
        Scene(testkit_api, hid).wait_for_accessible()
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()

        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=user_2.name.title(),
            password=user_2.password,
            )
        Scene(testkit_api, hid).wait_for_accessible()
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()


if __name__ == '__main__':
    exit(test_connect_to_system_with_specific_data().main())
