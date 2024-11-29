# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from tests.web_admin._nx_checkbox import NxCheckbox


class SystemSettings:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_auto_discovery(self) -> NxCheckbox:
        selector = ByXPATH("//nx-checkbox[@name='autoDiscoveryEnabled']")
        return NxCheckbox(self._browser.wait_element(selector, 10))

    def get_statistics_allowed(self) -> NxCheckbox:
        selector = ByXPATH("//nx-checkbox[@name='statisticsAllowed']")
        return NxCheckbox(self._browser.wait_element(selector, 10))

    def get_camera_settings_optimization(self) -> NxCheckbox:
        selector = ByXPATH("//nx-checkbox[@name='cameraSettingsOptimization']")
        return NxCheckbox(self._browser.wait_element(selector, 10))


class SecuritySettings:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_enable_audit_trail(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-checkbox[@name='auditTrailEnabled']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_traffic_force_encryption(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-checkbox[@name='trafficEncryptionForced']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_video_force_encryption(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-checkbox[@name='videoTrafficEncryptionForced']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_limit_session_duration(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-checkbox[@name='sessionLimitMinutesToggle']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_limit_session_duration_interval(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-numeric//input[@id='generic-numeric']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_time_unit_select(self) -> WebDriverElement:
        xpath = (
            "//nx-block[//header[contains(., 'Security')]]"
            "//nx-select//button[@id='serverTimeUnitSelect']"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)
