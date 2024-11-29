# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import ItemsView
from collections.abc import Mapping
from enum import Enum
from pathlib import PurePath
from typing import Union

from browser.color import RGBColor
from browser.css_properties import get_text_color
from browser.css_properties import get_width
from browser.html_elements import Button
from browser.html_elements import InputField
from browser.html_elements import Table
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import ElementNotInteractable
from browser.webdriver import MultipleElementsFound
from browser.webdriver import StaleElementReference
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from distrib import Version


class StorageLocations:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_storages_table(self) -> '_StoragesTable':
        storages_table = self._get_storages_table()
        result = {}
        space_field_index = _get_space_field_index(storages_table)
        space_field_selector = ByXPATH(
            "./nx-storage-size-component/div[contains(@class, 'container')]")
        for row in storages_table.get_non_empty_rows():
            storage_address_element = row[0]
            mode_field = row[1]
            space_field = space_field_selector.find_in(row[space_field_index])
            storage_path = PurePath(get_visible_text(storage_address_element))
            result[storage_path] = _Storage(storage_address_element, mode_field, space_field)
        return _StoragesTable(result)

    def get_add_external_storage_button(self) -> Button:
        xpath = "//nx-server-storage-component//button[contains(text(),'Add External Storage')]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def _get_storages_table(self) -> Table:
        storages_table_selector = ByXPATH("//form[@name='storageSettings']/table")
        return Table(self._browser.wait_element(storages_table_selector, 5))

    def get_detailed_info_button(self) -> Button:
        xpath = "//nx-server-storage-component//button[contains(., 'Detailed Info')]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


def _get_space_field_index(table: Table) -> int:
    # TODO: Re-consider replacing with a simple version check after 23.12.2024
    #  after all WebAdmin versions not containing changes from
    #  https://networkoptix.atlassian.net/browse/CLOUD-14820
    #  are gone.
    # There are multiple possible columns layouts:
    # 0         1       2           3       4
    # Address   Mode    Space                           # 6.1 (before refactor), 6.0, 5.1
    # Address   Mode    Space       Delete              # 6.1 (before refactor), 6.0, 5.1
    # Address   Mode    R\W Policy  Space               # 6.1 (after refactor)
    # Address   Mode    R\W Policy  Space   Delete      # 6.1 (after refactor)
    headers = table.get_columns()
    header_texts = {get_visible_text(column) for column in headers}
    delete_column_header = ' '
    return -2 if delete_column_header in header_texts else -1


class _StoragesTable:

    def __init__(self, storages_by_path: Mapping[PurePath, '_Storage']):
        self._storages_by_path = storages_by_path

    def find_storage_entry(self, path: Union[os.PathLike, str]) -> '_Storage':
        # Storage path being returned by API contains internal path part 'HD Witness Media',
        # while in WebAdmin interface this information is not present.
        for storage_path, storage in self._storages_by_path.items():
            if storage_path.is_relative_to(path):
                _logger.info("Path %s is relative to storage %s", path, storage_path)
                return storage
        available_paths = list(self._storages_by_path.keys())
        raise RuntimeError(f"Can't find a storage py path {path} amongst {available_paths}")

    def items(self) -> ItemsView[PurePath, '_Storage']:
        return self._storages_by_path.items()

    def __repr__(self):
        return f'<Storages: {list(self._storages_by_path.keys())}>'


class _Storage:

    def __init__(self, address: WebDriverElement, mode: WebDriverElement, space: WebDriverElement):
        self._address = address
        self._mode = mode
        self._space = space

    def get_icon(self) -> '_StorageIcon':
        return _StorageIcon(ByXPATH("./svg-icon").find_in(self._address))

    def get_mode(self) -> '_StorageMode':
        return _StorageMode(self._mode)

    def get_space(self) -> WebDriverElement:
        return self._space


class _StorageMode:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def invoke(self):
        self._element.invoke()

    def get_text(self) -> str:
        return get_visible_text(self._element)

    def get_text_color(self) -> RGBColor:
        return get_text_color(ByXPATH("./div").find_in(self._element))

    def get_dropdown(self) -> WebDriverElement:
        # TODO: Consider splitting 6.0.0 and 6.0.1 implementations after 06.12.2024.
        dropdown_xpath = "(.//nx-select | .//nx-select-v2)"
        return ByXPATH(dropdown_xpath).wait_in(self._element, 5)

    def get_warning_icon(self) -> VisibleElement:
        selector = ByXPATH(".//svg-icon[contains(@class, 'warning')]")
        return VisibleElement(selector.find_in(self._element))


class _StorageIcon:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def type(self) -> 'IconType':
        data_source = self._element.get_attribute('data-src')
        if data_source.endswith('storage_local.svg'):
            return IconType.LOCAL
        elif data_source.endswith('storage_network.svg'):
            return IconType.NETWORK
        elif data_source.endswith('storage_usb.svg'):
            return IconType.USB
        raise RuntimeError(f"Unknown type of storage icon. @data-src: {data_source!r}")

    def svg(self) -> str:
        return self._element.get_dom_string_property('innerHTML')


class IconType(Enum):

    NETWORK = 'network'
    LOCAL = 'local'
    USB = 'usb'


class SpaceBar:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def get_text(self) -> str:
        text_label = ByXPATH("div[contains(@class, 'total-label')]").find_in(self._element)
        return get_visible_text(text_label)

    def get_width_pixels(self) -> float:
        bar_element = ByXPATH("div[contains(@class, 'container-overlay')]").find_in(self._element)
        return get_width(bar_element)

    def get_legend(self, browser: Browser) -> '_StorageSpacesLegend':
        mouse = browser.request_mouse()
        visible_bar = VisibleElement(self._element)
        bar_center = visible_bar.get_bounding_rect().get_absolute_coordinates(0.5, 0.5)
        mouse.hover(bar_center)
        legend_selector = ByXPATH("//nx-popover//table[contains(@class, 'table-legend')]")
        return _StorageSpacesLegend(Table(browser.wait_element(legend_selector, 5)))


class _StorageSpacesLegend:

    def __init__(self, table: Table):
        self._table = table

    def get_spaces(self) -> Mapping[str, str]:
        result = {}
        for [_color_scheme_cell, name_cell, size_cell] in self._table.get_non_empty_rows():
            name = get_visible_text(name_cell)
            size_text = get_visible_text(size_cell)
            result[name] = size_text
        return result


class AddExternalStorageDialog:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_add_storage_button(self) -> Button:
        xpath = "//nx-modal-add-storage//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_cancel_button(self) -> Button:
        xpath = "//nx-modal-add-storage//button[@type='reset']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_url_field(self) -> InputField:
        selector = ByXPATH("//nx-modal-add-storage//input[@id='addUrl']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_login_field(self) -> InputField:
        selector = ByXPATH("//nx-modal-add-storage//input[@id='addLogin']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_password_field(self) -> InputField:
        selector = ByXPATH("//nx-modal-add-storage//input[@id='addPassword']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_close_button(self) -> Button:
        selector = ByXPATH("//nx-modal-add-storage//button[@aria-label='Close']")
        return Button(self._browser.wait_element(selector, 10))


def wait_storage_added_toast(browser: Browser, timeout: float):
    xpath = (
        "//nx-app-toasts"
        "//nx-toast"
        "//div["
        "contains(@class, 'alert-success') and contains(., 'External storage added')"
        "]"
        )
    browser.wait_element(ByXPATH(xpath), timeout)


def get_reindex_main_storage_button(browser: Browser) -> Button:
    selector = ByXPATH("//button[contains(text(),'Reindex Main Storage')]")
    return Button(browser.wait_element(selector, 10))


def storage_mode_choice_menu(browser: Browser, vms_version: Version) -> 'StorageModeChoiceMenu':
    if vms_version < (6, 0):
        return _StorageModeChoiceMenuV5(browser)
    elif (6, 0) <= vms_version < (6, 1):
        return _StorageModeChoiceMenuV60(browser)
    # TODO: The menu is refactored in 6.1. Re-consider need of this check after 01.12.2024 or
    #  disappearance of
    # https://artifactory.us.nxteam.dev/artifactory/build-vms-develop/master/6566/default/distrib/
    # See: https://networkoptix.atlassian.net/browse/CLOUD-15054
    if _v60_style_menu_present(browser):
        return _StorageModeChoiceMenuV60(browser)
    return _StorageModeChoiceMenuV61Plus(browser)


def _v60_style_menu_present(browser: Browser) -> bool:
    try:
        browser.wait_element(ByXPATH("//div[@aria-labelledby='storageModeSelect']"), 5)
    except ElementNotFound:
        return False
    except MultipleElementsFound:
        pass
    return True


class StorageModeChoiceMenu(metaclass=ABCMeta):

    @abstractmethod
    def get_main_entry(self) -> 'ModeChoiceEntry':
        pass

    @abstractmethod
    def get_backup_entry(self) -> 'ModeChoiceEntry':
        pass

    @abstractmethod
    def get_not_in_use_entry(self) -> 'ModeChoiceEntry':
        pass


class _StorageModeChoiceMenuV60(StorageModeChoiceMenu):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_main_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div["
            "@aria-labelledby='storageModeSelect' and "
            "not(contains(@style, 'display: none'))"
            "]"
            "//li[.//span[contains(text(), 'Main')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_backup_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div["
            "@aria-labelledby='storageModeSelect' and "
            "not(contains(@style, 'display: none'))"
            "]"
            "//li[.//span[contains(text(), 'Backup')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_not_in_use_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div["
            "@aria-labelledby='storageModeSelect' and "
            "not(contains(@style, 'display: none'))"
            "]"
            "//li[.//span[contains(text(), 'Not in use')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))


class _StorageModeChoiceMenuV5(StorageModeChoiceMenu):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_main_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//form[@name='storageSettings']"
            "//div[@aria-labelledby='genericSelect' and not(contains(@style, 'display: none'))]"
            "//li[.//span[contains(text(), 'Main')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_backup_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//form[@name='storageSettings']"
            "//div[@aria-labelledby='genericSelect' and not(contains(@style, 'display: none'))]"
            "//li[.//span[contains(text(), 'Backup')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_not_in_use_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//form[@name='storageSettings']"
            "//div[@aria-labelledby='genericSelect' and not(contains(@style, 'display: none'))]"
            "//li[.//span[contains(text(), 'Not in use')]]"
            )
        return ModeChoiceEntryV5(self._browser.wait_element(ByXPATH(xpath), 10))


class _StorageModeChoiceMenuV61Plus(StorageModeChoiceMenu):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_main_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//div[contains(@class, 'custom-dropdown-menu')]"
            "//nx-select-item[contains(., 'Main')]"
            )
        return ModeChoiceEntry61Plus(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_backup_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//div[contains(@class, 'custom-dropdown-menu')]"
            "//nx-select-item[contains(., 'Backup')]"
            )
        return ModeChoiceEntry61Plus(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_not_in_use_entry(self) -> 'ModeChoiceEntry':
        xpath = (
            "//div[contains(@class, 'cdk-overlay-container')]"
            "//div[contains(@class, 'custom-dropdown-menu')]"
            "//nx-select-item[contains(., 'Not in use')]"
            )
        return ModeChoiceEntry61Plus(self._browser.wait_element(ByXPATH(xpath), 10))


class ModeChoiceEntry(metaclass=ABCMeta):

    @abstractmethod
    def is_selected(self) -> bool:
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        pass

    @abstractmethod
    def choose(self):
        pass


class ModeChoiceEntryV5(ModeChoiceEntry):

    def __init__(self, element: WebDriverElement):
        self._element = element

    def is_selected(self) -> bool:
        try:
            ByXPATH(".//a[contains(@class, 'selected')]").find_in(self._element)
        except ElementNotFound:
            return False
        return True

    def is_enabled(self) -> bool:
        # A menu entry is built around an HTML hyperlink which is always active and can't be used
        # to the entry status determination
        try:
            ByXPATH(".//span[contains(@class, 'disabled')]").find_in(self._element)
        except ElementNotFound:
            return True
        return False

    def choose(self):
        # The menu is always present on the page but it and all its options are hidden.
        try:
            self._element.invoke()
        except ElementNotInteractable:
            raise ModeEntryNotFound()


class ModeChoiceEntry61Plus(ModeChoiceEntry):

    def __init__(self, element: WebDriverElement):
        self._element = element

    def is_selected(self) -> bool:
        return 'highlighted' in self._element.get_attribute('class')

    def is_enabled(self) -> bool:
        return 'disabled' not in self._element.get_attribute('class')

    def choose(self):
        try:
            self._element.invoke()
        except StaleElementReference:
            raise ModeEntryNotFound()


class ModeEntryNotFound(Exception):
    pass


_logger = logging.getLogger(__name__)
