# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from functools import lru_cache

from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit import TestKitConnectionError
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class TextNotFound(Exception):
    pass


class _SessionRefreshDialog:
    """Appears when we connect to cloud.

    Requires current user credentials to connect to the specified cloud account.
    """

    def __init__(self, api: TestKit, hid: HID):
        _session_refresh_dialog_locator = {
            "name": "MessageBox",
            "type": "nx::vms::client::desktop::SessionRefreshDialog",
            "visible": 1,
            }
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj=_session_refresh_dialog_locator)

    def connect(self, current_system_password):
        _logger.info('%r: Connect system to Cloud', self)
        cloud_tab_overlay = Widget(self._api, {
            "name": "CloudManagementWidget",
            "type": "QnCloudManagementWidget",
            "visible": 1,
            })
        password_qline = cloud_tab_overlay.find_child({
            "name": "passwordLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        QLineEdit(self._hid, password_qline).type_text(current_system_password)
        connect_button = self._dialog.find_child({
            "text": "Connect",
            "type": "nx::vms::client::desktop::BusyIndicatorButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(connect_button)
        MessageBox(self._api, self._hid).close_by_button('OK')
        self._dialog.wait_until_closed()


class CloudAuthConnect:
    """Class is responsible for user authorization to cloud and for cloud system connect.

    Its dialogs open when you click on:
    - connect system to nx cloud button in system administration dialog
    - cloud icon on top panel (user is logged in to nx server)
    - cloud tile on welcome screen (user is not logged in to nx server)
    """

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "type": "nx::vms::client::desktop::OauthLoginDialog",
            "unnamed": 1,
            "visible": 1,
            'occurrence': 1,
            })
        self._button_center = None
        self._api = api
        self._hid = hid

    def wait_for_text(self, expected_text, timeout: float = 3):
        _logger.info(
            '%r: Wait for text %s. Timeout: %s second(s)',
            self, expected_text, timeout)
        start_time = time.monotonic()
        while True:
            text_comparer = ImageTextRecognition(self.image_capture())
            if text_comparer.has_line(expected_text):
                return
            if time.monotonic() - start_time > timeout:
                raise TextNotFound(f"No text {expected_text!r} among actual text.")
            time.sleep(.5)

    def has_email(self, email):
        try:
            self.wait_for_text(email)
        except TextNotFound as e:
            if f"No text {email!r} among actual text" in str(e):
                return False
        return True

    def has_password_field(self):
        try:
            self.wait_for_text('Password')
        except TextNotFound as e:
            if "No text 'Password' among actual text" in str(e):
                return False
        return True

    @lru_cache(maxsize=2)
    def _get_field_center(self, field_name: str):
        word_rect = self._get_rectangle(field_name)
        return word_rect.center().down(40)

    def _get_next_button_center(self):
        word_rect = self._get_rectangle('Next')
        return word_rect.center()

    def _get_log_in_button_center(self):
        word_rect = self._get_rectangle('Log')
        return word_rect.center()

    def _get_rectangle(self, text: str):
        capture = self.image_capture()
        text_comparer = ImageTextRecognition(capture)
        word_rect = text_comparer.get_phrase_rectangle(text)
        return word_rect

    def _field_click(self, field_name: str):
        self._hid.mouse_left_click(self._get_field_center(field_name))

    def next_button_click(self):
        self.wait_for_text('Next')
        self._hid.mouse_left_click(self._get_next_button_center())

    def log_in_button_click(self):
        if self._button_center is not None:
            button_center = self._button_center
        else:
            button_center = self._get_log_in_button_center()
        self._hid.mouse_left_click(button_center)

    def insert_email(self, email):
        self.wait_for_text('Email')
        self._field_click('Email')
        self._hid.write_text(email)

    def insert_password(self, password):
        self.wait_for_text('Password')
        self._field_click('Password')
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.write_text(password)

    def _cloud_web_input(self, email, password, simplistic):
        """Workaround until we're able to work with WebEngine window type."""
        if not simplistic:
            self.insert_email(email)
            time.sleep(2)
            self.next_button_click()
            self.wait_for_text('Password')
        self.insert_password(password)
        time.sleep(2)
        self._hid.keyboard_hotkeys('Return')

    def connect_client(self, email, password):
        _logger.info('%r: Connect client to Cloud', self)
        self._cloud_web_input(email, password, simplistic=False)
        self._dialog.wait_for_inaccessible()

    def connect_system(self, email, password, current_system_password, simplistic):
        """Fill only password field if client is already connected to the Cloud."""
        _logger.info('%r: Connect system to Cloud', self)
        self._cloud_web_input(email, password, simplistic)
        self.wait_for_text("Connect system to")
        self._hid.keyboard_hotkeys('Return')
        self._dialog.wait_for_inaccessible()
        try:
            _SessionRefreshDialog(self._api, self._hid).connect(current_system_password)
        except TestKitConnectionError as e:
            raise RuntimeError(
                f"Client crashed: {e}. Maybe it is due to cross-system layouts bug. "
                f"See: https://networkoptix.atlassian.net/browse/VMS-55730")

    def connect_system_with_client_connected(self, password, current_system_password):
        _logger.info('%r: Connect system to Cloud with client connected', self)
        self._cloud_web_input(email=None, password=password, simplistic=True)
        self.wait_for_text("Connect system to")
        self._hid.keyboard_hotkeys('Return')
        self._dialog.wait_for_inaccessible()
        _SessionRefreshDialog(self._api, self._hid).connect(current_system_password)

    def close(self):
        _logger.info('%r: Close connect to Cloud Dialog', self)
        self._dialog.close()

    def image_capture(self):
        return self._dialog.image_capture()

    def is_accessible_timeout(self, timeout: float):
        return self._dialog.is_accessible_timeout(timeout)

    def wait_for_accessible(self):
        self._dialog.wait_for_accessible(timeout=10)
