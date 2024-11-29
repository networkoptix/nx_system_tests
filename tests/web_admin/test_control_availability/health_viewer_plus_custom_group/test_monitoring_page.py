# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import CameraPermissions
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV3
from mediaserver_api import ResourceGroups
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._monitoring import get_monitoring_graph
from tests.web_admin._monitoring import get_monitoring_menu
from tests.web_admin._monitoring import get_monitoring_servers
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_monitoring_page(WebAdminTest):
    """Test control availability.

    Selection-Tag: web-admin-gitlab
    See: https://networkoptix.atlassian.net/browse/FT-2181
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122608
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """Covers step 7 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
    one_vm_type = 'ubuntu22'
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    first_api: MediaserverApiV3 = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api: MediaserverApiV3 = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    first_api.setup_local_system()
    second_api.setup_local_system()
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
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
    custom_group_id = first_api.add_user_group(
        custom_group_name,
        permissions=['none'],
        resources_access_rights=full_access_rights,
        )
    custom_user_name = "custom_user"
    custom_user_password = "custom_user_password"
    first_api.add_multi_group_local_user(
        custom_user_name, custom_user_password, group_ids=[Groups.HEALTH_VIEWERS, custom_group_id])
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(custom_user_name)
    login_form.get_password_field().put(custom_user_password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_monitoring_link().invoke()
    monitoring_menu = get_monitoring_menu(browser)
    monitoring_menu.get_server_choice_button().invoke()
    get_monitoring_servers(browser)[first_server_name].invoke()
    monitoring_menu.get_graphs_link().invoke()
    _wait_monitoring_page_update(browser, timeout=10)
    assert not element_is_present(monitoring_menu.get_logs_link)


def _wait_monitoring_page_update(browser: Browser, timeout: float):
    graph = get_monitoring_graph(browser)
    timeout_at = time.monotonic() + timeout
    lines_hashes = set()
    while True:
        lines = graph.get_lines()
        lines_digest = hashlib.md5(''.join(lines).encode('utf-8')).hexdigest()
        lines_hashes.add(lines_digest)
        if len(lines_hashes) > 1:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(f"Monitoring graph is not updated after {timeout}")
        time.sleep(0.3)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_monitoring_page()]))
