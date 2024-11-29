# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from collections.abc import Sequence
from ipaddress import IPv4Address
from typing import Literal

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import TextField
from gui.testkit import TestKit
from gui.testkit.hid import HID


class LDAPConnectionSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(api, {'visible': True, 'type': 'ConnectionSettingsDialog'})
        self._hid = hid

    def fill_parameters(self, host: str | IPv4Address, admin_dn: str, password: str):
        self._fill_host(str(host))
        self._fill_login(admin_dn)
        self._fill_password(password)

    def _fill_host(self, host: str):
        _logger.info("%r: Fill host: '%s'", self, host)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'ldapUri',
            'type': 'TextFieldWithValidator',
            'visible': True,
            }))
        if host:
            text_field.type_text(host)
        else:
            text_field.clear()

    def _fill_login(self, admin_dn: str):
        _logger.info("%r: Fill login: '%s'", self, admin_dn)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'adminDnTextField',
            'type': 'TextFieldWithValidator',
            'visible': True,
            }))
        if admin_dn:
            text_field.type_text(admin_dn)
        else:
            text_field.clear()

    def _fill_password(self, password: str):
        _logger.info('%r: Fill password: "%s"', self, password)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'passwordTextField',
            'type': 'PasswordFieldWithWarning',
            'visible': True,
            }))
        if password:
            text_field.type_text(password)
        else:
            text_field.clear()

    def click_test_button(self):
        _logger.info('%r: Click test button', self)
        button = Button(self._widget.find_child({
            'text': 'Test',
            'id': 'testButton',
            'type': 'Button',
            }))
        self._hid.mouse_left_click(button.center())

    def set_ldap_scheme(self, scheme: Literal['ldap://', 'ldaps://']):
        _logger.info('%r: Set LDAP scheme %s', self, scheme)
        ldap_scheme_widget = self._widget.find_child({
            "id": "schemeCombobox",
            "type": "ComboBox",
            "visible": True,
            })
        combobox = _LdapSchemeComboBox(self._hid, ldap_scheme_widget)
        combobox.select(scheme)

    def click_ok(self):
        _logger.info('%r: Click OK button', self)
        button = Button(self._widget.find_child({
            'text': 'OK',
            'type': 'Button',
            }))
        self._hid.mouse_left_click(button.center())

    def get_error_message_text(self) -> str:
        test_status_label = self._widget.find_child({'visible': True, 'id': 'testStatus'})
        text_label = test_status_label.find_child({'visible': True, 'type': 'QQuickText'})
        return text_label.get_text()

    def get_warning_messages(self) -> Sequence[str]:
        text_labels = self._widget.find_children(
            {'visible': True, 'id': 'warningMessage', 'type': 'QQuickText'})
        return [label.get_text() for label in text_labels]


class _LdapSchemeComboBox:

    def __init__(self, hid: HID, widget: Widget):
        self._hid = hid
        self._widget = widget

    def _open(self):
        self._hid.mouse_left_click_on_object(self._widget)
        time.sleep(1)

    def _current_item(self) -> str:
        return str(self._widget.wait_property('currentText'))

    def select(self, item_text: str):
        if item_text != self._current_item():
            self._open()
            item = self._widget.find_child({
                'id': 'contentItem',
                'text': item_text,
                'visible': True,
                'enabled': True,
                })
            self._hid.mouse_left_click_on_object(item)


_logger = logging.getLogger(__name__)
