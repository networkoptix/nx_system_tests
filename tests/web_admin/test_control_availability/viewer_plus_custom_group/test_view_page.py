# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import CameraPermissions
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV3
from mediaserver_api import ResourceGroups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._cameras_view_page import CameraPreview
from tests.web_admin._cameras_view_page import get_server_entries
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_view_page(WebAdminTest):
    """Test control availability.

    Selection-Tag: web-admin-gitlab
    See: https://networkoptix.atlassian.net/browse/FT-2181
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122606
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack):
    """Covers step 5 from the case."""
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
    license_server_url = license_server.url()
    mediaserver_api.setup_local_system({'licenseServer': license_server_url})
    server_name = "server"
    mediaserver_api.rename_server(server_name)
    brand = mediaserver_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 1, 'CLASS2': 'digital', 'BRAND2': brand})
    mediaserver_api.activate_license(permanent_professional_key)
    custom_group_name = "Group1"
    full_resource_permissions = [
        CameraPermissions.VIEW_LIVE,
        CameraPermissions.VIEW_ARCHIVE,
        CameraPermissions.EXPORT_ARCHIVE,
        CameraPermissions.VIEW_BOOKMARKS,
        CameraPermissions.MANAGE_BOOKMARKS,
        CameraPermissions.USER_INPUT,
        CameraPermissions.EDIT,
        ]
    if distrib.newer_than('vms_6.0'):
        full_resource_permissions.append(CameraPermissions.AUDIO)
    full_access_rights = {ResourceGroups.ALL_DEVICES: full_resource_permissions}
    custom_group_id = mediaserver_api.add_user_group(
        custom_group_name,
        permissions=['none'],
        resources_access_rights=full_access_rights,
        )
    custom_user_name = "custom_user"
    custom_user_password = "custom_user_password"
    mediaserver_api.add_multi_group_local_user(
        custom_user_name, custom_user_password, group_ids=[Groups.VIEWERS, custom_group_id])
    active_camera_server = MultiPartJpegCameraServer()
    inactive_camera_server = MultiPartJpegCameraServer()
    [active_camera] = add_cameras(mediaserver, active_camera_server, indices=[0])
    [inactive_camera] = add_cameras(mediaserver, inactive_camera_server, indices=[1])
    with mediaserver_api.camera_recording(active_camera.id):
        active_camera_server.serve(time_limit_sec=5)
    exit_stack.enter_context(active_camera_server.async_serve())
    mediaserver_api.start_recording(active_camera.id)
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
    assert not server_entry.is_expanded()
    server_entry.expand()
    assert server_entry.is_expanded()
    camera_entries = server_entry.get_camera_entries()
    assert len(camera_entries) == 2
    active_camera_entry = camera_entries[active_camera.url]
    inactive_camera_entry = camera_entries[inactive_camera.url]
    active_camera_entry.open()
    assert active_camera_entry.is_opened()
    assert not inactive_camera_entry.is_opened()
    active_camera_preview = CameraPreview(browser)
    assert element_is_present(active_camera_preview.get_live_camera_archive)
    live_view = active_camera_preview.get_live()
    [single_source] = live_view.get_sources()
    _logger.info("Single camera source is %s", single_source)
    inactive_camera_entry.open()
    assert not active_camera_entry.is_opened()
    assert inactive_camera_entry.is_opened()
    browser.refresh()  # See: https://networkoptix.atlassian.net/browse/CLOUD-13086
    inactive_camera_preview = CameraPreview(browser)
    assert element_is_present(active_camera_preview.get_empty_archive)
    placeholder = _get_offline_placeholder(inactive_camera_preview, timeout=60)
    placeholder_text = get_visible_text(placeholder)
    status = 'OFFLINE'
    assert status in placeholder_text, f"{status!r} not in {placeholder_text!r}"


def _get_offline_placeholder(preview: CameraPreview, timeout: float) -> WebDriverElement:
    # After preview activation mediaserver tries to retrieve a stream from the camera.
    # This process takes some time before the camera is considered offline.
    end_at = time.monotonic() + timeout
    while True:
        try:
            element = preview.get_offline_placeholder()
        except ElementNotFound:
            if end_at < time.monotonic():
                raise RuntimeError(f"{preview} is not offline {timeout} sec")
            time.sleep(1)
            continue
        return element


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_view_page()]))
