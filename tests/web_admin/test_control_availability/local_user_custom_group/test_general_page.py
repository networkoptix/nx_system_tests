# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import assert_elements_absence
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_cloud import NxCloudForm
from tests.web_admin._system_name import SystemNameForm
from tests.web_admin._system_settings import SystemSettings
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_general_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    See: https://networkoptix.atlassian.net/browse/FT-2181
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122578
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver_api = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    expected_system_name = "Irrelevant_system"
    mediaserver_api.setup_local_system(name=expected_system_name)
    custom_group_name = "Custom_group"
    custom_group_id = mediaserver_api.add_user_group(
        custom_group_name, Permissions.NONADMIN_FULL_PRESET)
    custom_user_name = "custom_user"
    custom_user_password = "custom_user_password"
    mediaserver_api.add_local_user(
        custom_user_name, custom_user_password, group_id=custom_group_id)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(custom_user_name)
    login_form.get_password_field().put(custom_user_password)
    login_form.get_submit_button().invoke()
    upper_menu = UpperMenu(browser)
    main_menu = MainMenu(browser)
    assert upper_menu.get_view_link().is_active()
    assert upper_menu.get_settings_link().is_active()
    assert main_menu.get_system_administration_link().is_active()
    assert main_menu.get_cameras_link().is_active()
    system_settings = SystemSettings(browser)
    system_form = SystemNameForm(browser)
    assert_elements_absence(
        upper_menu.get_monitoring_link,
        upper_menu.get_information_link,
        main_menu.get_licenses_link,
        main_menu.get_servers_link,
        main_menu.get_users_link,
        system_settings.get_auto_discovery,
        system_settings.get_statistics_allowed,
        system_settings.get_camera_settings_optimization,
        system_form.get_merge_with_another_button,
        )
    nx_cloud_form = NxCloudForm(browser)
    expected_cloud_host = mediaserver_api.get_cloud_host()
    expected_cloud_url = f"https://{expected_cloud_host}/"
    cloud_host = nx_cloud_form.get_cloud_host_link().get_full_url()
    assert cloud_host == expected_cloud_url, f"{cloud_host} != {expected_cloud_host}"
    cloud_connect_link = nx_cloud_form.get_cloud_connect_link()
    assert not cloud_connect_link.get_full_url()
    cloud_connect_link_text = cloud_connect_link.get_text()
    expected_cloud_connect_link_text = "NOT CONNECTED"
    assert cloud_connect_link_text == expected_cloud_connect_link_text, (
        f"{cloud_connect_link_text} != {expected_cloud_connect_link_text}"
        )
    system_name_field = system_form.get_editable_name()
    system_name = system_name_field.get_current_value()
    assert system_name == expected_system_name, f"{system_name} != {expected_system_name}"
    permissions = system_form.get_permissions().get_text()
    assert permissions == custom_group_name, f"{permissions} != {custom_group_name}"
    assert not system_name_field.is_writable()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_general_page()]))
