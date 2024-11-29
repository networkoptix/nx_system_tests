# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from vm.networks import setup_flat_network


class test_login_failure(WebAdminTest):
    """Test login failure.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79737
    See: https://networkoptix.atlassian.net/browse/FT-2138
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    supplier = ClassicInstallerSupplier(args.distrib_url)
    mediaserver_pool = FTMachinePool(supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(mediaserver_pool.one_mediaserver('ubuntu22'))
    mediaserver_stand.mediaserver().start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[address, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    browser = exit_stack.enter_context(browser_stand.browser())
    mediaserver_web_url = mediaserver_stand.mediaserver().url(address)
    collect_version(browser, mediaserver_web_url)
    browser.open(mediaserver_web_url)
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    default_login_value = login_form.get_login_field().get_value()
    assert not default_login_value, f"{default_login_value!r} is not empty"
    default_password_value = login_form.get_password_field().get_value()
    assert not default_password_value, f"{default_password_value!r} is not empty"
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put("incorrect_password")
    login_form.get_submit_button().invoke()
    assert element_is_present(login_form.incorrect_password_badge)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_login_failure()]))
