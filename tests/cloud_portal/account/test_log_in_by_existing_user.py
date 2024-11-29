# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent


class test_log_in_by_existing_user(CloudTest):
    """Test log in by existing user.

    Selection-Tag: 94717
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94717
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        account = cloud_account_factory.create_account()
        services_hosts = account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())

        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(account.user_email, account.password)
        # Make sure the user is logged in - account dropdown should be available.
        assert element_is_present(header.account_dropdown)


if __name__ == '__main__':
    exit(test_log_in_by_existing_user().main())
