# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import CameraPermissions
from mediaserver_api import MediaserverApiV3
from mediaserver_api import ResourceGroups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._cameras import Camera
from tests.web_admin._cameras import CredentialsForm
from tests.web_admin._cameras import get_aspect_ratios
from tests.web_admin._cameras import get_rotations
from tests.web_admin._cameras_view_page import get_server_entries
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._main_menu import get_camera_entries
from tests.web_admin._nx_apply import NxApplyBar
from vm.networks import setup_flat_network


class test_cameras_page(WebAdminTest):
    """Test control availability.

    Selection-Tag: web-admin-gitlab
    See: https://networkoptix.atlassian.net/browse/FT-2181
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122609
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """Covers step 4 from the case."""
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
    brand = mediaserver_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 2, 'CLASS2': 'digital', 'BRAND2': brand})
    mediaserver_api.activate_license(permanent_professional_key)
    camera_server = MultiPartJpegCameraServer()
    add_cameras(mediaserver, camera_server, indices=[0])
    all_access_rights_group_name = "all_access_rights_group"
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
    all_access_rights_group_id = mediaserver_api.add_user_group(
        name=all_access_rights_group_name,
        permissions=['none'],
        resources_access_rights={ResourceGroups.ALL_DEVICES: full_resource_permissions},
        )
    no_access_rights_group_name = "no_access_rights_group"
    no_access_rights_group_id = mediaserver_api.add_user_group(
        name=no_access_rights_group_name,
        permissions=['none'],
        resources_access_rights={ResourceGroups.ALL_DEVICES: []},
        )
    custom_user_name = "custom_user"
    custom_user_password = "custom_user_password"
    mediaserver_api.add_multi_group_local_user(
        name=custom_user_name,
        password=custom_user_password,
        group_ids=[no_access_rights_group_id, all_access_rights_group_id],
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
    MainMenu(browser).get_cameras_link().invoke()
    cameras_entries = tuple(get_camera_entries(browser))
    assert len(cameras_entries) == 1, f"Only one camera should be present. Got: {cameras_entries}"
    camera_entry = cameras_entries[0]
    apply_bar = NxApplyBar(browser)
    camera_entry.open()
    assert camera_entry.is_opened()
    camera_component = Camera(browser)
    assert not element_is_present(camera_component.get_detailed_info_button)
    aspect_ratio_before = camera_component.get_aspect_ratio_button().get_text()
    _change_to_next_aspect_ratio(camera_component, browser)
    assert apply_bar.get_cancel_button().is_active()
    apply_bar.get_save_button().invoke()
    aspect_ratio_after = camera_component.get_aspect_ratio_button().get_text()
    assert aspect_ratio_after != aspect_ratio_before, (
        f"{aspect_ratio_after} != {aspect_ratio_before}"
        )
    rotation_angle_before = camera_component.get_rotation_angle_button().get_text()
    _change_to_next_rotation_angle(camera_component, browser)
    assert apply_bar.get_cancel_button().is_active()
    apply_bar.get_save_button().invoke()
    rotation_angle_after = camera_component.get_rotation_angle_button().get_text()
    assert rotation_angle_after != rotation_angle_before, (
        f"{rotation_angle_after} != {rotation_angle_before}"
        )
    # Motion detection validating is disabled due to unstable behavior.
    # motion_detection = MotionDetectionSettings(browser)
    # motion_detection.get_settings_button().invoke()
    # available_actions = motion_detection.get_actions()
    # assert len(available_actions) == 1, f"Expected single action, received {available_actions}"
    # available_actions['Disable Motion Detection'].invoke()
    # assert apply_bar.get_cancel_button().is_active()
    # apply_bar.get_save_button().invoke()
    # apply_bar.wait_apply()
    # motion_detection.get_enable_button().invoke()
    # assert apply_bar.get_cancel_button().is_active()
    # apply_bar.get_save_button().invoke()
    # See: https://networkoptix.atlassian.net/browse/CLOUD-13675
    camera_component.get_authentication_button().invoke()
    camera_credentials = CredentialsForm(browser)
    assert camera_credentials.get_cancel_button().is_active()
    irrelevant_login = "IRRELEVANT"
    camera_credentials.get_login_input().put(irrelevant_login)
    camera_credentials.get_password_input().put("IRRELEVANT")
    camera_credentials.get_save_button().invoke()
    camera_credentials.wait_disappearance(10)
    camera_component.get_authentication_button().invoke()
    login_after = camera_credentials.get_login_input().get_value()
    password_after = camera_credentials.get_password_input().get_value()
    assert login_after == irrelevant_login, f"{login_after!r} != {irrelevant_login!r}"
    assert set(password_after) == set("*"), f"Password is not masked: {password_after!r}"
    camera_credentials.get_cancel_button().invoke()
    # Editable name test is disabled due to unstable behavior.
    # camera_name_selector = ByXPATH("//nx-text-editable[@id='cameraName-editable']")
    # editable_name = EditableName(browser, camera_name_selector)
    # editable_name.set("IRRELEVANT")
    # assert apply_bar.get_cancel_button().is_active()
    # apply_bar.get_save_button().invoke()
    # editable_name_after = editable_name.get_current_value()
    # assert editable_name_after == "IRRELEVANT", f"Name is not 'IRRELEVANT': {editable_name_after}"
    # See: https://networkoptix.atlassian.net/browse/CLOUD-13692
    camera_component.get_view_button().invoke()
    server_menu_entries = get_server_entries(browser)
    assert len(server_menu_entries) == 1, f"Single server system, {server_menu_entries} received"


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
        # For unknown reason, rotation angle after was changed in the web interface is not changed.
        # Saving changes just after change a rotation angle won't save it. No anchors were found.
        # The feed picture rotation is not enough. Is not reproduced at manual testing.
        time.sleep(1)
        return
    raise RuntimeError(f"Couldn't find any available rotation angle among {available_angles}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_cameras_page()]))
