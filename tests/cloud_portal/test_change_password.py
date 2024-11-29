# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import StaleElementReference
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._change_pass import ChangePassForm
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._toast_notification import SuccessToast
from tests.cloud_portal._translation import en_us


class test_change_password(CloudTest):
    """Test change account password.

    Selection-Tag: 94721
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94721
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        language = en_us
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        # Assume that the page is ready if there is a message about no systems.
        assert element_is_present(SystemAdministrationPage(browser).get_no_systems_text), (
            "The main page isn't loaded in time after logging",
            )
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).change_password_option().invoke()
        change_pass = ChangePassForm(browser)
        change_pass.current_password_input().set_password(cloud_owner.password)
        new_password = "WellKnownPassword1 WithSpace"
        change_pass.new_password_input().set_password(new_password)
        change_pass.get_save_button().invoke()
        placeholder = change_pass.get_no_unsaved_changes_placeholder()
        assert placeholder.get_text() == language.tr('NO_UNSAVED_CHANGES')
        password_changed_toast = SuccessToast(browser)
        assert password_changed_toast.get_text() == language.tr('PASSWORD_SUCCESSFULLY_CHANGED')
        cloud_owner.set_password(new_password)  # To be able to remove the user on teardown
        password_changed_toast.wait_until_not_visible()
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        header = HeaderNav(browser)
        _invoke_live_log_in_link(header)
        LoginComponent(browser).login(cloud_owner.user_email, new_password)
        assert element_is_present(header.account_dropdown)


def _invoke_live_log_in_link(header: HeaderNav) -> None:
    timeout = 5
    started_at = time.monotonic()
    while True:
        try:
            header.get_log_in_link().invoke()
        except StaleElementReference:
            if time.monotonic() - started_at > timeout:
                raise
            _logger.debug(
                "Cannot invoke the Log In button - it became stale. "
                "Getting a fresh button and trying again after a delay")
            time.sleep(0.5)
        else:
            break


_logger = logging.getLogger()

if __name__ == '__main__':
    exit(test_change_password().main())
