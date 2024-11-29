# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from typing import Collection
from urllib.request import Request
from urllib.request import urlopen

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._download_page import DownloadsPage
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._history_page import HistoryPage
from tests.cloud_portal._login import LoginComponent


class test_downloads_history(CloudTest):
    """Test downloads history.

    Selection-Tag: 81199
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/81199
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
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        resources_link = header.get_services_link()
        resources_link.invoke()
        history_link = DownloadsPage(browser).get_other_releases_link()
        history_link.invoke()
        history_page = HistoryPage(browser)
        releases_tab = history_page.get_releases_tab()
        patches_tab = history_page.get_patches_tab()
        betas_tab = history_page.get_betas_tab()
        assert releases_tab.is_selected(), "Releases tab should be selected"
        download_links = history_page.get_download_links()
        assert len(download_links) > 5, "There should be many download links for Releases"
        for url in _filter_links_by_min_version(download_links):
            assert "updates.networkoptix.com" in url
            _verify_file_size_downloaded(url)
        patches_tab.invoke()
        assert patches_tab.is_selected(), "Patches tab should be selected"
        download_links = history_page.get_download_links()
        assert len(download_links) > 5, "There should be many download links for Patches"
        for url in _filter_links_by_min_version(download_links, 5.0):
            assert "updates.networkoptix.com" in url
            _verify_file_size_downloaded(url)
        betas_tab.invoke()
        assert betas_tab.is_selected(), "Betas tab should be selected"
        download_links = history_page.get_download_links()
        assert len(download_links) > 5, "There should be many download links for Betas"
        for url in _filter_links_by_min_version(download_links):
            assert "updates.networkoptix.com" in url
            _verify_file_size_downloaded(url)


def _filter_links_by_min_version(
        download_links: Collection,
        min_vms: float = 5.1,
        min_mobile: float = 23.1,
        ):
    """
    Filters out any links older than vms 5.1 and mobile client 23.1.

    Helps keep the runtime of this test reasonable while focusing on recent versions.
    """
    filtered_links = []
    vms_version_regex = re.compile(r'\d\.\d')
    mobile_version_regex = re.compile(r'\d\d\.\d')
    for link in download_links:
        destination = link.get_full_url()
        if "android" in destination or "ios" in destination:
            mobile_version = float(mobile_version_regex.search(destination).group())
            if mobile_version >= min_mobile:
                filtered_links.append(destination)
        else:
            vms_version = float(vms_version_regex.search(destination).group())
            if vms_version >= min_vms:
                filtered_links.append(destination)
    if len(filtered_links) < 1:
        raise RuntimeError(
            f"Found no links with a version > minimum: vms_{min_vms} mobile_{min_mobile}",
            )
    return filtered_links


def _verify_file_size_downloaded(url: str):
    with urlopen(Request(url, method='HEAD'), timeout=5) as response:
        content_length = int(response.headers.get('Content-Length', 0))
        if content_length < 1000:
            raise RuntimeError(f"File from {url} is too small")


if __name__ == '__main__':
    exit(test_downloads_history().main())
