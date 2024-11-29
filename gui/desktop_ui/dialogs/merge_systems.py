# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import EditableComboBox
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class MergeSystemsDialog:
    # nx::vms::client::desktop::MergeSystemsDialog

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "MergeSystemsDialog",
            "type": "nx::vms::client::desktop::MergeSystemsDialog",
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def _activate_merge(self, button_text_pattern: re.Pattern):
        merge_button = self._dialog.find_child({
            "text": button_text_pattern,
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(merge_button)

    def merge_with_configured_server(
            self,
            our_password: str,
            user: str,
            password: str,
            port: int,
            ip: str,
            site_name: str,
            ):
        _logger.info('%r: Start merging system with configured server', self)
        self._fill_url(f'https://{ip}:{port}')
        self._fill_login(user)
        self._fill_password(password)
        self._activate_test_connection()
        first_time_connect(self._api, self._hid)
        button_text_pattern = re.compile(f'Merge with {site_name}')
        self._activate_merge(button_text_pattern)
        _MergeSystemsRefreshDialog(self._api, self._hid).complete_the_merge(our_password)

    def merge_with_new_server(
            self,
            our_password: str,
            user: str,
            password: str,
            port: int,
            ip: str,
            ):
        _logger.info('%r: Start merging system with new server', self)
        self._fill_url(f'https://{ip}:{port}')
        self._fill_login(user)
        self._fill_password(password)
        self._activate_test_connection()
        first_time_connect(self._api, self._hid)
        button_text_pattern = re.compile('Merge with New (System|Site)')
        self._activate_merge(button_text_pattern)
        _MergeSystemsRefreshDialog(self._api, self._hid).complete_the_merge(our_password)

    def _fill_password(self, password: str):
        password_edit = QLineEdit(self._hid, self._dialog.find_child({
            "name": "passwordEdit_passwordLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))
        password_edit.type_text(password)

    def _fill_login(self, user: str):
        login_edit = QLineEdit(self._hid, self._dialog.find_child({
            "name": "loginEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))
        login_edit.type_text(user)

    def _fill_url(self, url: str):
        url_combo_box = EditableComboBox(self._dialog.find_child({
            "name": "urlComboBox",
            "type": "QComboBox",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(url_combo_box)
        self._hid.write_text(url)

    def _activate_test_connection(self):
        check_button = Button(self._dialog.find_child({
            "name": "testConnectionButton",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(check_button)


class _MergeSystemsRefreshDialog:
    # nx::vms::client::desktop::SessionRefreshDialog

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "MessageBox",
            "type": "nx::vms::client::desktop::SessionRefreshDialog",
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def complete_the_merge(self, our_password):
        _logger.info('%r: Finish merging systems', self)
        password_edit = QLineEdit(self._hid, self._dialog.find_child({
            "name": "passwordLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))
        password_edit.type_text(our_password)
        merge_button = Button(self._dialog.find_child({
            "text": "Merge",
            "type": "nx::vms::client::desktop::BusyIndicatorButton",
            "unnamed": 1,
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(merge_button)
        message_box = MessageBox(self._api, self._hid)
        message_box.wait_for_accessible(10)
        # Systems - VMS 6.0. Sites - 6.1 and higher.
        title_pattern = re.compile('(Systems|Sites) will be merged shortly')
        title_text = message_box.get_title()
        if title_pattern.match(message_box.get_title()) is None:
            raise RuntimeError(
                f'Unexpected message box title: {title_text!r}. '
                f'Expected pattern: {title_pattern.pattern!r}',
                )
        message_box.close_by_button('OK')
