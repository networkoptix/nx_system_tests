# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ByXPATH
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._translation import en_us


class test_content_libraries(CloudTest):
    """Test content libraries page.

    Selection-Tag: 109687
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/109687
    """

    def _run(self, args, exit_stack):
        language = en_us
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/content/libraries")
        text = language.tr('OPEN_SOURCE_SOFTWARE_DISCLOSURE')
        page_title_selector = ByXPATH.quoted(
            '//h1[@class="ng-star-inserted" and starts-with(text(), %s)]',
            text,
            )
        browser.wait_element(page_title_selector, 20)


if __name__ == '__main__':
    exit(test_content_libraries().main())
