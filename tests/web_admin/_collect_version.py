# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import get_visible_text
from directories import get_run_dir


def collect_version(browser: Browser, mediaserver_root_url: str) -> None:
    # By unknown reasons, developers do not provide another way to obtain WebAdmin version.
    # Extracting version information from distrib URL requires downloading and unpacking
    # a ZIP archive that is considered unnecessarily complex and resource-consuming.
    browser.open(mediaserver_root_url.rstrip("/") + "/static/version.txt")
    element = browser.wait_element(ByXPATH("/html/body"), 5)
    text = get_visible_text(element)
    (get_run_dir() / 'web_admin_version.txt').write_text(text)
