# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.dialogs.connect_to_cloud import CloudAuthConnect
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CloudPanel:

    def __init__(self, api: TestKit, hid: HID):
        _main_window_locator = {
            "type": "nx::vms::client::desktop::MainWindow",
            "unnamed": 1,
            "visible": 1,
            }
        self._obj = Widget(api, {
            "type": "QnCloudStatusPanel",
            "unnamed": 1,
            "visible": 1,
            "window": _main_window_locator,
            })
        self._api = api
        self._hid = hid

    def is_logged_in(self):
        return self.get_email() not in ('', 'Logging in...')

    def wait_for_logged_in(self, timeout: float = 10):
        _logger.info('%r: Wait for logged in. Timeout: %s second(s)', self, timeout)
        start_time = time.monotonic()
        while True:
            if self.is_logged_in():
                return
            msg_box = MessageBox(self._api, self._hid)
            if msg_box.is_accessible_timeout(0.1):
                if msg_box.has_label('Your session has expired'):
                    raise RuntimeError(
                        '"Session Expired" dialog has appeared. '
                        'See: https://networkoptix.atlassian.net/browse/VMS-52639',
                        )
            if time.monotonic() - start_time > timeout:
                raise RuntimeError("Cloud panel is not in logged in state")
            time.sleep(1)

    def get_email(self):
        return self._obj.get_text()

    def open_login_to_cloud_dialog(self) -> CloudAuthConnect:
        _logger.info('%r: Open Login to Cloud Dialog', self)
        self._hid.mouse_left_click_on_object(self._obj)
        cloud_dialog = CloudAuthConnect(self._api, self._hid)
        cloud_dialog.wait_for_accessible()
        return cloud_dialog

    def logout(self):
        _logger.info('%r: Log out from Nx Cloud', self)
        self._hid.mouse_left_click_on_object(self._obj)
        QMenu(self._api, self._hid).activate_items("Log out from Nx Cloud")
        if self.is_logged_in():
            raise RuntimeError("User is still logged in Nx Cloud")

    def login(self, email: str, password: str, cloud_name: str):
        _logger.info('%r: Log in to %s', self, cloud_name)
        cloud_auth = self.open_login_to_cloud_dialog()
        cloud_auth.wait_for_text(f'Log in to {cloud_name}', timeout=25)
        cloud_auth.connect_client(email, password)

    def is_accessible(self):
        return self._obj.is_accessible_timeout(3)

    def wait_for_inaccessible(self):
        self._obj.wait_for_inaccessible()

    def wait_for_accessible(self):
        self._obj.wait_for_accessible()

    def image_capture(self):
        return self._obj.image_capture()
