# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections.abc import Mapping

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


def get_users(browser: Browser) -> Mapping[str, '_UserMenuEntry']:
    users = {}
    users_list_container = browser.wait_element(ByXPATH("//div[@id='level3users']"), 10)
    user_selector = ByXPATH(".//nx-level-3-item/a[contains(@href, '/settings/users')]")
    name_selector = ByXPATH(".//span[contains(@class, 'user')]//nx-search-highlight")
    for user_element in user_selector.find_all_in(users_list_container):
        name_element = name_selector.find_in(user_element)
        name = get_visible_text(name_element)
        user_id = user_element.get_attribute("id")
        users[name] = _UserMenuEntry(browser, user_id)
    return users


class _UserMenuEntry:

    def __init__(self, browser: Browser, id_: str):
        self._browser = browser
        self._id = id_

    def _get_entry_element(self) -> WebDriverElement:
        selector = ByXPATH.quoted("//div[@id='level3users']//a[@id=%s]", self._id)
        return self._browser.wait_element(selector, 10)

    def is_opened(self) -> bool:
        element = self._get_entry_element()
        class_attribute = element.get_attribute("class")
        return "selected" in class_attribute

    def get_current_group_name(self) -> str:
        entry_element = self._get_entry_element()
        entry_text = get_visible_text(entry_element)
        [_user_name, group_name] = entry_text.split('\N{EN DASH}')
        return group_name

    def open(self):
        self._get_entry_element().invoke()

    def __repr__(self):
        return f'<UserEntry: {self._id}>'


class UserForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_username(self) -> str:
        selector = ByXPATH("//nx-system-user-component//header")
        name_element = self._browser.wait_element(selector, 10)
        return get_visible_text(name_element)

    def get_group(self) -> str:
        group_selector = ByXPATH("//nx-system-user-component//div[contains(@class, 'group-name')]")
        group_element = self._browser.wait_element(group_selector, 10)
        return get_visible_text(group_element)

    def get_name_field(self) -> InputField:
        selector = ByXPATH("//nx-system-user-component//input[@id='fullName']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_email_field(self) -> InputField:
        selector = ByXPATH("//nx-system-user-component//input[@id='email']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_change_password(self) -> Button:
        selector = ByXPATH("//nx-system-user-component//button[contains(., 'Change Password')]")
        return Button(self._browser.wait_element(selector, 10))

    def get_delete_button(self) -> Button:
        selector = ByXPATH("//nx-system-user-component//button[contains(., 'Delete User')]")
        return Button(self._browser.wait_element(selector, 10))

    def get_change_group_button(self) -> Button:
        selector = ByXPATH("//nx-system-user-component//button[@id='edit-user-groups']")
        return Button(self._browser.wait_element(selector, 10))

    def get_remove_button(self) -> Button:
        # Cloud Users use "Remove" term for the user removal process instead of "Delete"
        # because users are not deleted as such but their access to the system is revoked.
        # See: https://networkoptix.atlassian.net/wiki/spaces/FS/pages/1713308353/User+Management+Web
        # See: https://english.stackexchange.com/questions/52508/difference-between-delete-and-remove
        selector = ByXPATH("//nx-system-user-component//button[contains(., 'Remove User')]")
        return Button(self._browser.wait_element(selector, 10))


class DeleteUserModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_delete_button(self) -> Button:
        xpath = "//cdk-dialog-container//nx-modal-remove-user-content//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


class UserCredentialsForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_cancel_button(self) -> Button:
        selector = ByXPATH("//nx-modal-change-password//nx-cancel-button//button[@type='reset']")
        return Button(self._browser.wait_element(selector, 10))

    def get_save_button(self) -> Button:
        selector = ByXPATH("//nx-modal-change-password//nx-process-button//button[@type='submit']")
        return Button(self._browser.wait_element(selector, 10))

    def get_current_password_input(self) -> InputField:
        selector = ByXPATH("//nx-modal-change-password//input[@id='currentPassword']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_new_password_input(self) -> InputField:
        selector = ByXPATH("//nx-modal-change-password//input[@id='newPassword']")
        return InputField(self._browser.wait_element(selector, 10))

    def get_new_password_confirmation_input(self) -> InputField:
        selector = ByXPATH("//nx-modal-change-password//input[@id='confirmNewPassword']")
        return InputField(self._browser.wait_element(selector, 10))


def get_password_changed_badge(browser: Browser) -> WebDriverElement:
    toast_selector = ByXPATH(
        "//nx-app-toasts//nx-toast[contains(., 'Password successfully changed')]")
    return browser.wait_element(toast_selector, 10)


def get_available_groups(browser: Browser) -> Mapping[str, Button]:
    groups = {}
    groups_list_xpath = "//nx-system-user-component//div[@aria-labelledby='edit-user-groups']"
    groups_list_container = browser.wait_element(ByXPATH(groups_list_xpath), 10)
    group_name_selector = ByXPATH(".//li[contains(@class, 'dropdown-item-container')]")
    for group_element in group_name_selector.find_all_in(groups_list_container):
        group_name = get_visible_text(group_element)
        groups[group_name] = Button(group_element)
    return groups


def get_add_user_button(browser: Browser) -> Button:
    selector = ByXPATH("//nx-system-settings-component//nx-menu//button[contains(., 'Add User')]")
    return Button(browser.wait_element(selector, 10))


class AddUserDialog:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_permission_group_button(self) -> Button:
        selector = ByXPATH("//nx-modal-add-user-content//button[@id='addUserDialogGroupsSelect']")
        return Button(self._browser.wait_element(selector, 10))

    def get_permission_group_entries(self) -> Mapping[str, WebDriverElement]:
        menu_xpath = (
            "//nx-modal-add-user-content"
            "//div[@aria-labelledby='addUserDialogGroupsSelect']"
            )
        menu_element = self._browser.wait_element(ByXPATH(menu_xpath), 10)
        entry_selector = ByXPATH(".//li[.//nx-checkbox]")
        result = {}
        for entry_element in entry_selector.find_all_in(menu_element):
            group_name = get_visible_text(entry_element)
            result[group_name] = entry_element
        return result

    def get_close_button(self) -> Button:
        selector = ByXPATH("//nx-modal-add-user-content//button[@aria-label='Close']")
        return Button(self._browser.wait_element(selector, 10))


class GroupNames:
    ADVANCED_VIEWERS = "Advanced Viewers"
    POWER_USERS = "Power Users"
    LIVE_VIEWERS = "Live Viewers"
    HEALTH_VIEWERS = "Health Viewers"
    VIEWERS = "Viewers"
