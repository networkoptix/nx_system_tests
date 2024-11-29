# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._ipvd import IPVDPage
from tests.cloud_portal._translation import en_us


class test_ipvd_page(CloudTest):
    """Test Supported Devices page.

    Selection-Tag: 57509
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57509
    """

    def _run(self, args, exit_stack):
        language = en_us
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/ipvd/"
        browser.open(link)
        header = HeaderNav(browser)
        active_tab_name = header.get_active_tab_name()
        assert active_tab_name == language.tr("SUPPORTED_DEVICES_TAB")
        ipvd = IPVDPage(browser, language)
        assert element_is_present(ipvd.get_search_icon)
        assert element_is_present(ipvd.get_cloud_logo)
        assert element_is_present(ipvd.get_advanced_search_button)
        assert element_is_present(ipvd.get_manufacturers_pane)
        assert element_is_present(ipvd.get_devices_pane)
        assert element_is_present(ipvd.get_submit_request_link)


if __name__ == '__main__':
    exit(test_ipvd_page().main())
