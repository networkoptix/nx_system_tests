# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import TextField
from gui.testkit import TestKit
from gui.testkit.hid import HID


class ConnectToServer:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(
            api,
            {'visible': True, 'enabled': True, 'name': 'customConnectionScreen'},
            )
        self._hid = hid

    def _fill_host_and_port_field(self, ip, port):
        _logger.info('%r: Fill host and port field', self)
        filed_widget = self._widget.find_child({
            'id': 'addressField',
            'type': 'TextField',
            'visible': True,
            'enabled': True,
            })
        self._hid.mouse_left_click(filed_widget.center())
        self._hid.write_text(f'{ip}:{port}')

    def _fill_login_field(self, login):
        _logger.info('%r: Fill login field', self)
        filed_widget = self._widget.find_child({
            'id': 'loginField',
            'type': 'TextField',
            'visible': True,
            'enabled': True,
            })
        self._hid.mouse_left_click(filed_widget.center())
        self._hid.write_text(login)

    def _fill_password_field(self, password):
        _logger.info('%r: Fill password field', self)
        field_widget = self.get_password_field()
        self._hid.mouse_left_click(field_widget.bounds().center())
        self._hid.write_text(password)

    def click_connect_button(self):
        _logger.info('%r: Click connect button', self)
        button = Button(self._widget.find_child({
            'id': 'connectButton',
            'type': 'LoginButton',
            'visible': True,
            'enabled': True,
            }))
        self._hid.mouse_left_click(button.center())

    def connect(self, ip: str, port: int, username: str, password: str):
        self._fill_host_and_port_field(ip, port)
        self._fill_login_field(username)
        self._fill_password_field(password)
        self.click_connect_button()

    def get_password_field(self) -> TextField:
        field_widget = self._widget.find_child({
            'id': 'passwordField',
            'type': 'TextField',
            'visible': True,
            })
        return TextField(self._hid, field_widget)

    def clear_saved_password(self):
        _logger.info('%r: Clear password field', self)
        cross_button_locator = {
            'name': 'image',
            'type': 'QQuickIconImage',
            'source': 'qrc:////images/clear.png',
            'visible': True,
            }
        button = self._widget.find_child(cross_button_locator)
        self._hid.mouse_left_click(button.center())

    def get_warning_text(self) -> str:
        widget = self._widget.find_child({
            'id': 'passwordErrorPanel',
            'visible': True,
            'text': re.compile(r'.+')})
        return widget.get_text()

    def click_back_button(self):
        _logger.info('%r: Click back button', self)
        button = Button(self._widget.find_child({'id': 'leftButton', 'type': 'IconButton'}))
        self._hid.mouse_left_click(button.center())


_logger = logging.getLogger(__name__)
