# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Callable
from typing import Any
from typing import Collection
from typing import Mapping
from typing import TypeVar

from browser.color import RGBColor
from browser.css_properties import get_visible_color
from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import StaleElementReference
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from distrib import Distrib
from tests.web_admin._nx_editable_name import EditableName


def get_servers(browser: Browser) -> Mapping[str, '_ServerMenuEntry']:
    result = {}
    servers_list_container = browser.wait_element(ByXPATH("//div[@id='level3servers']"), 10)
    server_selector = ByXPATH(".//nx-level-3-item/a[contains(@href, '/settings/servers')]")
    name_selector = ByXPATH(".//span[contains(@class, 'menu-level-3-label')]//nx-search-highlight")
    for server_element in server_selector.find_all_in(servers_list_container):
        name_element = name_selector.find_in(server_element)
        name = get_visible_text(name_element)
        server_id = server_element.get_attribute("id")
        result[name] = _ServerMenuEntry(browser, server_id)
    return result


_T = TypeVar('_T')


# A server entry in the Main menu is being renewed from time to time,
# so access to any entry may fail regardless of its WebDriverElement age.
# Adding timeouts only worsens the situation.
def _retry_at_stale_element(func: Callable[[Any, ...], _T]):

    def _wrapper(*args: Any, **kwargs: Any) -> _T:
        for index in range(3):
            try:
                return func(*args, **kwargs)
            except StaleElementReference:
                attempt = index + 1
                _logger.warning(
                    "Attempt %s to call %s(*%s, **%s) failed", attempt, func, args, kwargs)
                time.sleep(index * 0.1)

    return _wrapper


class _ServerMenuEntry:

    def __init__(self, browser: Browser, id_: str):
        self._browser = browser
        self._id = id_

    def _get_entry_element(self) -> WebDriverElement:
        selector = ByXPATH.quoted("//div[@id='level3servers']//a[@id=%s]", self._id)
        return self._browser.wait_element(selector, 10)

    @_retry_at_stale_element
    def is_opened(self) -> bool:
        element = self._get_entry_element()
        class_attribute = element.get_attribute("class")
        return "selected" in class_attribute

    @_retry_at_stale_element
    def open(self):
        self._get_entry_element().invoke()

    def __repr__(self):
        return f'<ServerEntry: {self._id}>'


class ServerSettings:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_port(self) -> InputField:
        selector = ByXPATH("//nx-block//nx-numeric//input[@id='server-port-numeric']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_analytics_storage_dropdown_button(self) -> Button:
        selector = ByXPATH("//nx-select//button[@id='serverAnalyticsSelect']")
        return Button(self._browser.wait_element(selector, 10))

    def get_detach_from_system_button(self) -> Button:
        selector = ByXPATH("//button[./span[contains(text(),'Detach from the System')]]")
        return Button(self._browser.wait_element(selector, 10))

    def get_reset_to_defaults_button(self) -> Button:
        selector = ByXPATH("//button[./span[contains(text(),'Reset to Defaults')]]")
        return Button(self._browser.wait_element(selector, 10))

    def get_restart_button(self) -> Button:
        xpath = "//nx-standard-server-component//span[contains(text(),'Restart')]/parent::button"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_detailed_info_button(self) -> Button:
        xpath_template = "//nx-standard-server-component//span[contains(text(),%s)]/parent::button"
        selector = ByXPATH.quoted(xpath_template, "Detailed Info")
        return Button(self._browser.wait_element(selector, 10))

    def get_server_offline_badge(self) -> WebDriverElement:
        xpath = "//nx-standard-server-component//nx-alert-block[contains(., 'Server offline')]"
        return self._browser.wait_element(ByXPATH(xpath), 10)

    def get_check_status_button(self) -> Button:
        xpath = (
            "//nx-standard-server-component"
            "//nx-alert-block"
            "//button[contains(., 'Check Status')]"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_server_restarting_badge(self) -> '_RestartBadge':
        xpath = "//nx-standard-server-component//nx-alert-block[@id='restarting']"
        return _RestartBadge(self._browser.wait_element(ByXPATH(xpath), 10))


class _RestartBadge:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def get_color(self) -> RGBColor:
        badge_div = ByXPATH(".//div[contains(@class, 'simple-info')]")
        # NX blue info color is achieved by blending multiple shades of light-grey and blue.
        return get_visible_color(badge_div.find_in(self._element))


class RestartDialog(metaclass=ABCMeta):

    @abstractmethod
    def get_restart_button(self) -> Button:
        pass

    @abstractmethod
    def get_cancel_button(self) -> Button:
        pass

    @abstractmethod
    def get_close_button(self) -> Button:
        pass


def get_restart_dialog(browser: Browser, distrib: Distrib) -> RestartDialog:
    if distrib.older_than('vms_6.0'):
        return RestartDialogV51(browser)
    return RestartDialogV60Plus(browser)


class RestartDialogV60Plus(RestartDialog):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_restart_button(self) -> Button:
        xpath = "//cdk-dialog-container//nx-modal-restart-server-content//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_cancel_button(self) -> Button:
        xpath = "//cdk-dialog-container//nx-modal-restart-server-content//button[@type='reset']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_close_button(self) -> Button:
        xpath = (
            "//cdk-dialog-container"
            "//nx-modal-restart-server-content"
            "//button[@aria-label='Close']"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


class RestartDialogV51(RestartDialog):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_restart_button(self) -> Button:
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//nx-modal-restart-server-content"
            "//button[@type='submit']"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_cancel_button(self) -> Button:
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//nx-modal-restart-server-content"
            "//button[@type='reset']"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_close_button(self) -> Button:
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//nx-modal-restart-server-content"
            "//button[@aria-label='Close']"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


def get_storages_for_analytics(browser: Browser) -> Collection['_StorageEntry']:
    menu_selector = ByXPATH("//div[@aria-labelledby='serverAnalyticsSelect']")
    dropdown_menu = browser.wait_element(menu_selector, 10)
    return [_StorageEntry(element) for element in ByXPATH(".//a").find_all_in(dropdown_menu)]


class _StorageEntry:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def in_use(self) -> bool:
        class_attribute = self._element.get_attribute("class")
        return "selected" in class_attribute

    def choose(self):
        self._element.invoke()


def get_server_name(browser: Browser) -> EditableName:
    selector = ByXPATH(
        "//nx-standard-server-component//nx-text-editable[@id='serverName-editable']")
    return EditableName(browser, selector)


_logger = logging.getLogger(__name__)
