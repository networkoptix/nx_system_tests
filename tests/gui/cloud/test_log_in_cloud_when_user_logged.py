# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.cloud_panel import CloudAuthConnect
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.desktop_ui.dialogs.connect_to_cloud import TextNotFound
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import CloudTest
from tests.base_test import VMSTest


class test_log_in_cloud_when_user_logged(VMSTest, CloudTest):
    """Connect system to cloud when cloud user is logged in.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6763
    Unstable because of https://networkoptix.atlassian.net/browse/VMS-52639
    XFAIL because of https://networkoptix.atlassian.net/browse/VMS-55927

    Selection-Tag: unstable
    Selection-Tag: xfail
    Selection-Tag: 6763
    Selection-Tag: cloud
    """

    def _run(self, args, exit_stack):
        cloud_account_factory = make_cloud_account_factory(args.cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())
        cloud_services_hosts = cloud_user.get_services_hosts()
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_for_cloud_tests(
                args.cloud_host,
                services_hosts=cloud_services_hosts,
                ),
            )
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        cloud_panel = CloudPanel(testkit_api, hid)
        cloud_name = get_cms_settings(args.cloud_host).get_cloud_name()
        cloud_panel.login(cloud_user.user_email, cloud_user.password, cloud_name)
        cloud_panel.wait_for_logged_in()
        cloud_panel_email = cloud_panel.get_email()
        assert cloud_panel_email == cloud_user.user_email, (
            f'Expect email in Cloud Panel: {cloud_user.user_email}, '
            f'Actual: {cloud_panel_email}'
            )
        main_menu = MainMenu(testkit_api, hid)
        system_administration_dialog = main_menu.activate_system_administration()
        system_administration_dialog.open_tab('Nx Cloud')
        cloud_auth_dialog = system_administration_dialog.cloud_tab.open_cloud_connection_window()
        try:
            cloud_auth_dialog.wait_for_text(cloud_user.user_email, timeout=15)
        except TextNotFound as e:
            if _has_account_not_exists_error_text(cloud_auth_dialog):
                raise RuntimeError(
                    '"Account does not exist" message has appeared. '
                    'See: https://networkoptix.atlassian.net/browse/VMS-55927',
                    )
            else:
                raise e
        assert cloud_auth_dialog.has_password_field()
        # TODO: Add missing email check.
        password = server_vm.api.get_credentials().password
        cloud_auth_dialog.connect_system_with_client_connected(
            cloud_user.password,
            password)
        assert system_administration_dialog.cloud_tab.get_connected_account() == cloud_user.user_email
        user_management_dialog = main_menu.activate_user_management()
        user_data = user_management_dialog.get_user_data_by_name(cloud_user.user_email)
        assert user_data['groups'] == "Administrators"
        # TODO: Add Cloud Portal check part.


def _has_account_not_exists_error_text(cloud_auth_dialog: CloudAuthConnect) -> bool:
    try:
        cloud_auth_dialog.wait_for_text('Account does not exist', timeout=0.5)
    except TextNotFound:
        return False
    return True


if __name__ == '__main__':
    exit(test_log_in_cloud_when_user_logged().main())
