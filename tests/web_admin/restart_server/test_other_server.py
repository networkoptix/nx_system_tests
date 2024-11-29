# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.color import RGBColor
from browser.webdriver import ElementNotFound
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import MediaserverApiV2
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._servers import ServerSettings
from tests.web_admin._servers import get_restart_dialog
from tests.web_admin._servers import get_servers
from vm.networks import setup_flat_network


class test_other_server(WebAdminTest):
    """Restart server (multi-server system, user is connected to another server of the system).

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84276
    See: https://networkoptix.atlassian.net/browse/CLOUD-14833
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # Test is slightly changed. The uptime check is performed via API, not via Chrome DevTools.
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    one_vm_type = 'ubuntu22'
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    first_api: MediaserverApiV2 = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api: MediaserverApiV2 = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    first_api.setup_local_system()
    second_api.setup_local_system()
    first_server_name = "first"
    second_server_name = "second"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    browser = exit_stack.enter_context(browser_stand.browser())
    mediaserver_web_url = first_mediaserver.url(first_mediaserver_ip)
    collect_version(browser, mediaserver_web_url)
    browser.open(mediaserver_web_url)
    local_administrator_credentials = first_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    server_settings = ServerSettings(browser)
    servers_entries = get_servers(browser)
    servers_entries[second_server_name].open()
    server_settings.get_restart_button().invoke()
    uptime_before_cancel = second_api.get_server_uptime_sec()
    get_restart_dialog(browser, distrib).get_cancel_button().invoke()
    uptime_after_cancel = second_api.get_server_uptime_sec()
    assert uptime_before_cancel < uptime_after_cancel, (
        f"{uptime_before_cancel} >= {uptime_after_cancel}"
        )
    server_settings.get_restart_button().invoke()
    uptime_before_close = second_api.get_server_uptime_sec()
    get_restart_dialog(browser, distrib).get_close_button().invoke()
    uptime_after_close = second_api.get_server_uptime_sec()
    assert uptime_before_close < uptime_after_close, (
        f"{uptime_before_close} >= {uptime_after_close}"
        )
    # Shades of blue match is difficult due to the color nature. The mathematical distance from
    # pure blue to either black or white is further than the mathematical distance between
    # black and white.
    nx_info_blue = RGBColor(179, 205, 255)
    with second_api.waiting_for_restart():
        server_settings.get_restart_button().invoke()
        get_restart_dialog(browser, distrib).get_restart_button().invoke()
        restart_badge = server_settings.get_server_restarting_badge()
        restart_badge_color = restart_badge.get_color()
        assert restart_badge_color.is_close_to(nx_info_blue), (
            f"{restart_badge_color!r} is far from {nx_info_blue!r}"
            )
        assert not server_settings.get_restart_button().is_active()
        try:
            assert not server_settings.get_detach_from_system_button().is_active()
        except AssertionError:
            if distrib.older_than('vms_6.0'):
                error_message = (
                    "'Detach from System' button is available. "
                    "See: https://networkoptix.atlassian.net/browse/CLOUD-14833"
                    )
                _logger.warning(error_message)
            else:
                raise
        try:
            assert not server_settings.get_reset_to_defaults_button().is_active()
        except AssertionError:
            if distrib.older_than('vms_6.0'):
                error_message = (
                    "'Reset to Defaults' button is available. "
                    "See: https://networkoptix.atlassian.net/browse/CLOUD-14833"
                    )
                _logger.warning(error_message)
            else:
                raise
        try:
            assert not server_settings.get_port().is_active()
        except AssertionError:
            if distrib.older_than('vms_6.0'):
                error_message = (
                    "'Port' field is writable. "
                    "See: https://networkoptix.atlassian.net/browse/CLOUD-14833"
                    )
                _logger.warning(error_message)
            else:
                raise
    _wait_restarting_badge_disappearance(server_settings, timeout=30)
    assert server_settings.get_restart_button().is_active()
    assert server_settings.get_detach_from_system_button().is_active()
    assert server_settings.get_reset_to_defaults_button().is_active()
    assert server_settings.get_port().is_active()


def _wait_restarting_badge_disappearance(server_settings: ServerSettings, timeout: float):
    timeout_at = time.monotonic() + timeout
    while True:
        try:
            server_settings.get_server_restarting_badge()
        except ElementNotFound:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(f"Restarting badge did not disappear after {timeout}")
        time.sleep(1)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_other_server()]))
