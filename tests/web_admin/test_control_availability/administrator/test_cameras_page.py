# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._cameras import Camera
from tests.web_admin._cameras import CredentialsForm
from tests.web_admin._cameras import get_aspect_ratios
from tests.web_admin._cameras import get_rotations
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._main_menu import get_camera_entries
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._nx_editable_name import EditableName
from vm.networks import setup_flat_network


class test_cameras_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122513
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """Covers step 3 from the case."""
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
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    brand = mediaserver_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 2, 'CLASS2': 'digital', 'BRAND2': brand})
    mediaserver_api.activate_license(permanent_professional_key)
    camera_server = MultiPartJpegCameraServer()
    add_cameras(mediaserver, camera_server, indices=[0, 1])
    # Serve in background to avoid page reload at camera status change.
    exit_stack.enter_context(camera_server.async_serve())
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_cameras_link().invoke()
    first_camera_entry, second_camera_entry = tuple(get_camera_entries(browser))
    apply_bar = NxApplyBar(browser)
    camera_name_selector = ByXPATH("//nx-text-editable[@id='cameraName-editable']")

    first_camera_entry.open()
    assert first_camera_entry.is_opened()
    assert not second_camera_entry.is_opened()
    first_camera_component = Camera(browser)
    assert first_camera_component.get_detailed_info_button().is_active()
    assert first_camera_component.get_view_button().is_active()
    _change_to_next_aspect_ratio(first_camera_component, browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    _change_to_next_rotation_angle(first_camera_component, browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    first_camera_component.get_authentication_button().invoke()
    CredentialsForm(browser).get_cancel_button().invoke()
    EditableName(browser, camera_name_selector).set("IRRELEVANT")
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()

    second_camera_entry.open()
    assert second_camera_entry.is_opened()
    assert not first_camera_entry.is_opened()
    second_camera_component = Camera(browser)
    assert second_camera_component.get_detailed_info_button().is_active()
    assert second_camera_component.get_view_button().is_active()
    _change_to_next_aspect_ratio(second_camera_component, browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    _change_to_next_rotation_angle(second_camera_component, browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    first_camera_component.get_authentication_button().invoke()
    CredentialsForm(browser).get_cancel_button().invoke()
    EditableName(browser, camera_name_selector).set("IRRELEVANT")
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()


def _change_to_next_aspect_ratio(camera: Camera, browser: Browser):
    aspect_ratio_button = camera.get_aspect_ratio_button()
    current_aspect_ratio_name = aspect_ratio_button.get_text()
    aspect_ratio_button.invoke()
    available_aspect_ratios = get_aspect_ratios(browser)
    for name, available_aspect_ratio in available_aspect_ratios.items():
        if name == current_aspect_ratio_name:
            continue
        available_aspect_ratio.invoke()
        return
    raise RuntimeError(f"Couldn't find any available aspect ratio among {available_aspect_ratios}")


def _change_to_next_rotation_angle(camera: Camera, browser: Browser):
    rotation_angle_button = camera.get_rotation_angle_button()
    current_rotation_angle = rotation_angle_button.get_text()
    rotation_angle_button.invoke()
    available_angles = get_rotations(browser)
    for name, available_rotation_angle in available_angles.items():
        if name == current_rotation_angle:
            continue
        available_rotation_angle.invoke()
        return
    raise RuntimeError(f"Couldn't find any available rotation angle among {available_angles}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_cameras_page()]))
