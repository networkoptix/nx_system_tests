# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class EULA:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_terms_and_conditions_text(self) -> None:
        text = self._translation_table.tr("TERMS_AND_CONDITIONS")
        path = "//nx-content-component//h1[contains(text(), %s)]"
        self._browser.wait_element(ByXPATH.quoted(path, text), 20)
