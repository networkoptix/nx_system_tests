# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Callable
from urllib.request import Request
from urllib.request import urlopen

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._download_version_page import DownloadsVersion
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us

_logger = logging.getLogger(__name__)


class test_downloads_version(CloudTest):
    """Test downloads page for different versions.

    Selection-Tag: 84523
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84523
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
        _wait_until_logged_in(header.account_dropdown)
        full_test_errors = {}
        errors_31398 = _get_downloads_version_errors(cloud_host, browser, '31398')
        if errors_31398:
            full_test_errors.update(errors_31398)
        errors_5_0_0_35745 = _get_downloads_version_errors(cloud_host, browser, '5.0.0.35745')
        if errors_5_0_0_35745:
            full_test_errors.update(errors_5_0_0_35745)
        errors_35745 = _get_downloads_version_errors(cloud_host, browser, '35745')
        if errors_35745:
            full_test_errors.update(errors_35745)
        assert not full_test_errors, f"Errors found: {full_test_errors!r}"


def _wait_until_logged_in(page_element_getter: Callable):
    try:
        page_element_getter()
    except ElementNotFound:
        raise RuntimeError("Page timed out or login failed")


def _get_downloads_version_errors(
        cloud_host, browser, version: str,
        translation_table: TranslationTable = en_us,
        ) -> dict:
    errors_dict = {}
    errors_list = []
    browser.open(f"https://{cloud_host}/downloads/{version}")
    downloads_version = DownloadsVersion(browser, translation_table)
    title_text = downloads_version.get_version_title().get_text()
    title_error = f"Version {version!r} not found in title {title_text!r}"
    _logger.debug("Check if %s", title_error)
    if version not in title_text:
        errors_list.append(title_error)
        _logger.debug("Error found in %s: %s", version, title_error)
    headers = downloads_version.get_release_notes_headers()
    base_msg = f"release notes headers {headers!r}"
    improvements = translation_table.tr('IMPROVEMENTS')
    improvements_error = f"{improvements!r} not found in {base_msg}"
    _logger.debug("Check if %s", improvements_error)
    if improvements not in headers:
        errors_list.append(improvements_error)
        _logger.debug("Error found in %s: %s", version, improvements_error)
    bug_fixes = translation_table.tr('BUG_FIXES')
    bug_fixes_error = f"{bug_fixes!r} not found in {base_msg}"
    _logger.debug("Check if %s", bug_fixes_error)
    if bug_fixes not in headers:
        errors_list.append(bug_fixes_error)
        _logger.debug("Error found in %s: %s", version, bug_fixes_error)
    links = downloads_version.get_download_links()
    # Check limited number of links to avoid triggering the DDoS guard.
    for i in range(2):
        file_url = links[i].get_full_url()
        file_url_error = f"Could not find {version!r} in {file_url!r}"
        _logger.debug("Check if %s", file_url_error)
        if version not in file_url:
            errors_list.append(file_url_error)
            _logger.debug("Error found in %s: %s", version, file_url_error)
        min_size_bytes = 1000
        file_size_bytes = _get_size_bytes(file_url)
        size_errors = f"{file_url} size {file_size_bytes}B is less than {min_size_bytes}B expected"
        _logger.debug("Check if %s", size_errors)
        if _get_size_bytes(file_url) <= min_size_bytes:
            errors_list.append(size_errors)
            _logger.debug("Error found in %s: %s", version, size_errors)
    if errors_list:
        errors_dict.update({f"{version}": errors_list})
    return errors_dict


def _get_size_bytes(file_url: str) -> int:
    with urlopen(Request(file_url, method='HEAD'), timeout=5) as response:
        return int(response.headers.get('Content-Length', 0))


if __name__ == '__main__':
    exit(test_downloads_version().main())
