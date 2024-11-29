# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_scenarios.merging import merge_systems
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


class test_ubuntu22(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122569
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_pages_control_availability(args, 'ubuntu22', exit_stack)


def _test_pages_control_availability(args, one_vm_type: str, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    first_api = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    license_server_url = license_server.url()
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    brand = first_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 1, 'CLASS2': 'digital', 'BRAND2': brand})
    first_api.activate_license(permanent_professional_key)
    viewer = "viewer"
    viewer_password = "viewer_password"
    first_api.add_local_user(viewer, viewer_password, group_id=Groups.VIEWERS)
    active_camera_server = MultiPartJpegCameraServer()
    inactive_camera_server = MultiPartJpegCameraServer()
    [active_camera] = add_cameras(first_mediaserver, active_camera_server, indices=[0])
    [inactive_camera] = add_cameras(first_mediaserver, inactive_camera_server, indices=[1])
    exit_stack.enter_context(active_camera_server.async_serve())
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(viewer)
    login_form.get_password_field().put(viewer_password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_view_link().invoke()
    server_menu_entries = get_server_entries(browser)
    first_server_entry = server_menu_entries[first_server_name]
    second_server_entry = server_menu_entries[second_server_name]
    assert first_server_entry.has_cameras()
    assert not second_server_entry.has_cameras()
    assert not first_server_entry.is_expanded()
    first_server_entry.expand()
    assert first_server_entry.is_expanded()
    camera_entries = first_server_entry.get_camera_entries()
    assert len(camera_entries) == 2
    active_camera_entry = camera_entries[active_camera.url]
    inactive_camera_entry = camera_entries[inactive_camera.url]
    active_camera_entry.open()
    assert active_camera_entry.is_opened()
    assert not inactive_camera_entry.is_opened()
    active_camera_preview = CameraPreview(browser)
    assert _has_access_to_archive(active_camera_preview)
    live_view = active_camera_preview.get_live()
    [single_source] = live_view.get_sources()
    _logger.info("Single camera source is %s", single_source)
    inactive_camera_entry.open()
    assert not active_camera_entry.is_opened()
    assert inactive_camera_entry.is_opened()
    # Camera changes its status to offline with a huge delay. Refresh to enforce status update.
    # See: https://networkoptix.atlassian.net/browse/CLOUD-13086
    browser.refresh()
    inactive_camera_preview = CameraPreview(browser)
    assert _has_access_to_archive(inactive_camera_preview)
    placeholder = _get_offline_placeholder(inactive_camera_preview, 60)
    placeholder_text = get_visible_text(placeholder)
    status = 'OFFLINE'
    assert status in placeholder_text, f"{status!r} not in {placeholder_text!r}"


def _get_offline_placeholder(preview: CameraPreview, timeout: float) -> WebDriverElement:
    # After preview activation mediaserver tries to retrieve a stream from the camera.
    # This process takes some time before the camera is considered offline.
    end_at = time.monotonic() + timeout
    while True:
        try:
            return preview.get_offline_placeholder()
        except ElementNotFound:
            if end_at < time.monotonic():
                raise RuntimeError(f"{preview} is not offline after {timeout} sec")
            time.sleep(1)


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
    exit(run_ft_test(sys.argv, [test_ubuntu22()]))
