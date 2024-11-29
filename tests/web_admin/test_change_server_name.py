# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import MediaserverApiV2
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._servers import get_server_name
from vm.networks import setup_flat_network


class test_change_server_name(WebAdminTest):
    """Server name appears correctly in WebAdmin after change.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85433
    See: https://networkoptix.atlassian.net/browse/FT-2371
    See: https://networkoptix.atlassian.net/browse/CLOUD-14780
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # The test is slightly altered. The testcase is created having manual testing in mind,
    # so it uses Desktop client to change a name.
    supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver_api: MediaserverApiV2 = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    expected_server_name = "ARBITRARY_NAME"
    single_server_id = mediaserver_api.get_server_id()
    # It is agreed with QA team lead to use API instead of Desktop client to change
    # a server name to avoid extra dependencies.
    mediaserver_api.rename_server(expected_server_name, single_server_id)
    delay = 30
    _logger.info("In accordance with the testcase, wait %s seconds after name change  ...", delay)
    time.sleep(delay)
    current_server_name = get_server_name(browser).get_current_value()
    try:
        assert current_server_name == expected_server_name, (
            f"{current_server_name!r} != {expected_server_name!r}"
            )
    except AssertionError:
        raise RuntimeError((
            f"{current_server_name!r} != {expected_server_name!r}. "
            "See: https://networkoptix.atlassian.net/browse/CLOUD-14780"
            ))


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_change_server_name()]))
