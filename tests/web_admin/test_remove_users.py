# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import StaleElementReference
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import CameraPermissions
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV3
from mediaserver_api import ResourceGroups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._users import DeleteUserModal
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_remove_users(WebAdminTest):
    """Remove local users via WebAdmin.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122532
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # The test is slightly altered. The testcase is created having manual testing in mind,
    # so it uses the Desktop client to change a name. It is agreed with QA team lead to use
    # the Mediaserver API instead of the Desktop client to validate the users list.
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
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    mediaserver_api.add_local_user(
        power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    advanced_viewer_name = "advanced_viewer"
    advanced_viewer_password = "advanced_viewer_password"
    mediaserver_api.add_local_user(
        advanced_viewer_name, advanced_viewer_password, group_id=Groups.ADVANCED_VIEWERS)
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
    viewer_name = "viewer"
    viewer_password = "viewer_password"
    mediaserver_api.add_multi_group_local_user(
        viewer_name, viewer_password, group_ids=[Groups.VIEWERS, custom_group_id])
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_users_link().invoke()
    _remove_user(power_user_name, browser)
    _remove_user(advanced_viewer_name, browser)
    _remove_user(viewer_name, browser)
    [expected_single_user] = mediaserver_api.list_users()
    assert expected_single_user.name == local_administrator_credentials.username, (
        f"{expected_single_user.name!r} != {local_administrator_credentials.username!r}"
        )


def _remove_user(name: str, browser: Browser):
    get_users(browser)[name].open()
    # Clicking on Delete button just after it's appearance makes user entries to not disappear
    # after removal. It is not reproducible manually due to impossibility for a user to comply
    # with tight timings. No anchors on the page were found.
    time.sleep(1)
    UserForm(browser).get_delete_button().invoke()
    DeleteUserModal(browser).get_delete_button().invoke()
    _wait_user_removed(name, browser, timeout=5)


def _wait_user_removed(name: str, browser: Browser, timeout: float):
    timeout_at = time.monotonic() + timeout
    while True:
        try:
            users = get_users(browser)
        except StaleElementReference:
            _logger.debug("One of key elements is reloaded.")
            if time.monotonic() > timeout_at:
                raise RuntimeError(f"User {name!r} is not removed after {timeout} sec")
            continue
        if name not in users:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(f"User {name!r} is not removed after {timeout} sec: {users}")
        time.sleep(0.3)


_logger = logging.getLogger(__file__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_remove_users()]))
