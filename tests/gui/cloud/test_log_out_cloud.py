# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import CloudTest
from tests.base_test import VMSTest


class test_log_out_cloud(VMSTest, CloudTest):
    """Log out from cloud.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/764
    Unstable because of https://networkoptix.atlassian.net/browse/VMS-52639

    Selection-Tag: unstable
    Selection-Tag: 764
    Selection-Tag: cloud
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [_, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_for_cloud_tests(
                args.cloud_host,
                services_hosts=[],
                ),
            )
        cloud_account_factory = make_cloud_account_factory(args.cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())

        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
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
        cloud_panel.logout()
        assert not cloud_panel.is_logged_in()
        cloud_login_dialog = cloud_panel.open_login_to_cloud_dialog()
        assert cloud_login_dialog.has_password_field()
        # Sometimes full email text is not recognized correctly.
        # To handle this we check the last part of the email, like: sendemail@networkoptix.com.
        user_email_part = cloud_user.user_email.split('+')[-1]
        assert cloud_login_dialog.has_email(user_email_part)


if __name__ == '__main__':
    exit(test_log_out_cloud().main())
