# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QSpinBox
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ConnectToServerDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "LoginDialog",
            "type": "nx::vms::client::desktop::LoginDialog",
            "visible": 1,
            "occurrence": 1,
            })

    def _get_button_by_text(self, text):
        button = self._dialog.find_child({
            "text": text,
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(button)

    def _get_field_by_object_name(self, name):
        field = self._dialog.find_child({
            "name": name,
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, field)

    def _get_host_field(self):
        return self._get_field_by_object_name("hostnameLineEdit")

    def _get_login_field(self):
        return self._get_field_by_object_name("loginLineEdit")

    def _get_password_field(self):
        return self._get_field_by_object_name("passwordEdit_passwordLineEdit")

    def _get_port_spinbox(self):
        port_spinbox = self._dialog.find_child({
            "name": "portSpinBox",
            "type": "QSpinBox",
            "visible": 1,
            })
        return QSpinBox(self._hid, port_spinbox)

    def connect(self, address, user, password, port):
        _logger.info('Connect to server')

        self._get_host_field().type_text(address)
        self._get_login_field().type_text(user)
        self._get_password_field().type_text(password)
        self._get_port_spinbox().type_text(str(port))
        self._hid.mouse_left_click_on_object(self._get_button_by_text("OK"))

    def cancel(self):
        _logger.info('Cancel connection to server')
        self._dialog.wait_for_accessible()
        self._hid.mouse_left_click_on_object(self._get_button_by_text("Cancel"))
        self._dialog.wait_until_closed()


def first_time_connect(api: TestKit, hid: HID):
    window = BaseWindow(api=api, locator_or_obj={
        "name": "MessageBox",
        "type": "nx::vms::client::desktop::ServerCertificateWarning",
        "visible": 1,
        })
    if window.is_accessible_timeout(1.5):
        _logger.info('Accept first time connect warning dialog')
        continue_button = window.find_child({
            "text": "Continue",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        hid.mouse_left_click_on_object(continue_button)
    else:
        _logger.debug("First time connect warning dialog didn't appear.")
