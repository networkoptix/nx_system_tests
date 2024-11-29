# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import CameraPermissions
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
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


class test_control_availability(WebAdminTest):
    """Test control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/123909
    See: https://networkoptix.atlassian.net/browse/CLOUD-13634
    """

    def _run(self, args, exit_stack: ExitStack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        distrib = installer_supplier.distrib()
        distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
        mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        browser_stand = exit_stack.enter_context(chrome_stand([]))
        [[mediaserver_ip, _], _] = setup_flat_network(
            [mediaserver_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver_api: MediaserverApiV3 = mediaserver_stand.api()
        mediaserver = mediaserver_stand.mediaserver()
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        mediaserver.start()
        upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
        mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
        first_server_name = "first_server"
        mediaserver_api.rename_server(first_server_name)
        brand = mediaserver_api.get_brand()
        permanent_professional_key = license_server.generate(
            {'QUANTITY2': 1, 'CLASS2': 'digital', 'BRAND2': brand})
        mediaserver_api.activate_license(permanent_professional_key)
        camera_server = MultiPartJpegCameraServer()
        [live_camera, view_and_edit_camera] = add_cameras(mediaserver, camera_server, indices=[0, 1])
        custom_user_name = "custom_user"
        custom_user_password = "custom_user_password"
        live_view_permissions = [CameraPermissions.VIEW_LIVE]
        view_and_edit_permissions = [
            CameraPermissions.VIEW_LIVE,
            CameraPermissions.VIEW_ARCHIVE,
            CameraPermissions.EDIT,
            ]
        mediaserver_api.add_local_user(
            custom_user_name,
            custom_user_password,
            resources_access_rights={
                live_camera.id: live_view_permissions,
                view_and_edit_camera.id: view_and_edit_permissions,
                },
            )
        expected_system_name = "Irrelevant_system"
        mediaserver_api.rename_site(expected_system_name)
        # Serve in background to avoid page reload at camera status change.
        exit_stack.enter_context(camera_server.async_serve())
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
            upper_menu.get_information_link,
            upper_menu.get_monitoring_link,
            main_menu.get_licenses_link,
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
        system_form = SystemNameForm(browser)
        system_name_field = system_form.get_editable_name()
        system_name = system_name_field.get_current_value()
        assert system_name == expected_system_name, f"{system_name} != {expected_system_name}"
        permissions = system_form.get_permissions().get_text()
        assert permissions == "Custom", f"{permissions} is not Custom"
        assert not system_name_field.is_writable()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_control_availability()]))
