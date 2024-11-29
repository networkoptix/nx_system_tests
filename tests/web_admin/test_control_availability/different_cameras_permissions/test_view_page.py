# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
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
from tests.web_admin._cameras_view_page import CameraPreview
from tests.web_admin._cameras_view_page import get_server_entries
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_control_availability(WebAdminTest):
    """Test control availability.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/123909
    See: https://networkoptix.atlassian.net/browse/CLOUD-13634
    See: https://networkoptix.atlassian.net/browse/CLOUD-13698
    """

    def _run(self, args, exit_stack: ExitStack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        distrib = installer_supplier.distrib()
        distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
        first_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        browser_stand = exit_stack.enter_context(chrome_stand([]))
        [[mediaserver_ip, _], _] = setup_flat_network(
            [first_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver_api: MediaserverApiV3 = first_stand.api()
        mediaserver = first_stand.mediaserver()
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        mediaserver.start()
        upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
        mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
        server_name = "single_server"
        mediaserver_api.rename_server(server_name)
        brand = mediaserver_api.get_brand()
        permanent_professional_key = license_server.generate(
            {'QUANTITY2': 2, 'CLASS2': 'digital', 'BRAND2': brand})
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
        # Serve in background to avoid page reload at camera status change.
        exit_stack.enter_context(camera_server.async_serve())
        browser = exit_stack.enter_context(browser_stand.browser())
        collect_version(browser, mediaserver.url(mediaserver_ip))
        browser.open(mediaserver.url(mediaserver_ip))
        login_form = LoginForm(browser)
        login_form.get_login_field().put(custom_user_name)
        login_form.get_password_field().put(custom_user_password)
        login_form.get_submit_button().invoke()
        UpperMenu(browser).get_view_link().invoke()
        server_menu_entries = get_server_entries(browser)
        server_entry = server_menu_entries[server_name]
        assert server_entry.has_cameras()
        server_entry.expand()
        assert server_entry.is_expanded()
        camera_entries = server_entry.get_camera_entries()
        assert len(camera_entries) == 2, f"Only two cameras expected, got {camera_entries}"
        live_camera_entry = camera_entries[live_camera.url]
        live_archive_camera_entry = camera_entries[view_and_edit_camera.url]
        live_camera_entry.open()
        assert live_camera_entry.is_opened()
        assert not live_archive_camera_entry.is_opened()
        active_camera_preview = CameraPreview(browser)
        assert not _has_access_to_archive(active_camera_preview)
        live_view = active_camera_preview.get_live()
        [single_source] = live_view.get_sources()
        _logger.info("Live View camera source is %s", single_source)
        live_archive_camera_entry.open()
        assert not live_camera_entry.is_opened()
        assert live_archive_camera_entry.is_opened()
        live_archive_camera_preview = CameraPreview(browser)
        assert _has_access_to_archive(live_archive_camera_preview)
        live_view = live_archive_camera_preview.get_live()
        [single_source] = live_view.get_sources()
        _logger.info("Live View and Archive camera source is %s", single_source)


def _has_access_to_archive(camera_preview: CameraPreview) -> bool:
    archive_control_element = camera_preview.get_archive_controls()
    empty_archive_selector = ByXPATH(".//span[contains(text(), 'No Archive')]")
    try:
        empty_archive_selector.find_in(archive_control_element)
    except ElementNotFound:
        return False
    return True


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_control_availability()]))
