# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from urllib.request import Request
from urllib.request import urlopen

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import WebDriverError
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._download_page import DownloadsPage
from tests.cloud_portal._footer import Footer
from tests.cloud_portal._translation import en_us

_logger = logging.getLogger()


class test_download_page(CloudTest):
    """Test download page.

    Selection-Tag: 30821
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30821
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())

        browser.open(f"https://{cloud_host}")
        footer = Footer(browser)
        downloads_link = footer.get_link_by_text(en_us.tr("DOWNLOADS"))
        _invoke_when_available(downloads_link, 5)
        downloads = DownloadsPage(browser)
        downloads.get_windows_client_installer_hyperlink().invoke()
        windows_link = downloads.get_download_hyperlink()
        _check_download_link(windows_link.get_full_url())
        downloads.get_mac_client_installer_hyperlink().invoke()
        mac_link = downloads.get_download_hyperlink()
        _check_download_link(mac_link.get_full_url())
        downloads.get_linux_client_installer_hyperlink().invoke()
        linux_link = downloads.get_download_hyperlink()
        _check_download_link(linux_link.get_full_url())
        playstore_link = downloads.get_play_store_hyperlink()
        actual_url = playstore_link.get_full_url()
        # The path for this link is taken from the CMS and its default value is "disabled".
        expected_url = f'https://{cloud_host}/disabled'
        assert actual_url == expected_url, f"{actual_url} does not match expected {expected_url}"
        itunes_link = downloads.get_itunes_store_hyperlink()
        actual_url = itunes_link.get_full_url()
        assert actual_url == expected_url, f"{actual_url} does not match expected {expected_url}"


def _invoke_when_available(hyperlink, timeout: float):
    # A link can be visible before it is interactable and, if invoked too soon,
    # it will lead to a ElementNotInteractable exception.
    started_at = time.monotonic()
    while True:
        try:
            hyperlink.invoke()
            break
        except WebDriverError:
            _logger.debug("Waiting for the element to be interactable")
            if time.monotonic() - started_at > timeout:
                raise
            time.sleep(0.3)


def _check_download_link(url: str):
    with urlopen(Request(url, method='HEAD'), timeout=5) as response:
        content_length = int(response.headers.get('Content-Length', 0))
        if content_length < 1000:
            raise RuntimeError(f"File {url} is too small")


if __name__ == '__main__':
    exit(test_download_page().main())
