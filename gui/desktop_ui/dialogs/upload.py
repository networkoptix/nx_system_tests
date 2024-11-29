# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _BaseUploadDialog(BaseWindow):

    def __init__(self, api: TestKit, hid: HID, dialog_locator):
        super().__init__(api, dialog_locator)
        self._hid = hid

    def _get_file_name_field(self):
        return QLineEdit(self._hid, Widget(self._api, {
            "name": "fileNameEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))

    def _close_file_dialog(self, button: Button):
        _logger.info('%r: Close', self)
        self._hid.mouse_left_click_on_object(button)
        if button.is_accessible():
            # If a tooltip with suggested path is appeared.
            self._hid.mouse_left_click_on_object(button)
        self.wait_for_inaccessible()

    def upload(self, path: str, button, time_sleep: int = 10):
        self._get_file_name_field().type_text(path)
        self._close_file_dialog(button())
        if time_sleep > 0:
            _logger.info('%r: Wait until file uploaded: %s second(s)', self, time_sleep)
            uploading_tile = NotificationsRibbon(self._api, self._hid).get_uploading_tile()
            # Upload can be very fast, then uploading_tile will be None.
            if uploading_tile:
                uploading_tile.wait_upload_stops(time_sleep)

    def get_open_button(self):
        return Button(self.find_child({'text': 'Open', 'type': 'QPushButton'}))

    def get_choose_button(self):
        return Button(self.find_child({'text': 'Choose', 'type': 'QPushButton'}))

    def upload_file(self, file_path: str, time_sleep: int = 10):
        _logger.info('%r: Upload file %s', self, file_path)
        self.upload(file_path, self.get_open_button, time_sleep)


class UploadDialog(_BaseUploadDialog):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api=api, hid=hid, dialog_locator={
            "name": "QFileDialog",
            "type": "QFileDialog",
            "visible": 1,
            "occurrence": 1,
            })

    def upload_folder(self, folder_path: str, time_sleep: int = 10):
        _logger.info('%r: Upload folder %s', self, folder_path)
        self.upload(folder_path, self.get_choose_button, time_sleep)

    def multi_upload_files(self, files_path: list, time_sleep: int = 10):
        _logger.info('%r: Upload folders %s', self, files_path)
        files = self._join_paths(files_path)
        self.upload(files, self.get_upload_button, time_sleep)

    @staticmethod
    def _join_paths(paths):
        return ' '.join([UploadDialog._quote_path(path) for path in paths])

    @staticmethod
    def _quote_path(path):
        # Qt does not do any escaping.
        # See: https://github.com/qt/qtbase/blob/f5b1dbb8f6966bea54799480e3c16e23f0d06d42/src/widgets/dialogs/qfiledialog.cpp#L1167
        return '"' + str(path) + '"'

    def is_file_dialog(self) -> bool:
        combo_box = self.find_child({
            "name": "fileTypeCombo",
            "type": "QComboBox",
            "visible": 1,
            })
        return combo_box.is_accessible_timeout(0.5)

    def get_upload_button(self):
        if self.is_file_dialog():
            return self.get_open_button()
        else:
            return self.get_choose_button()


class CustomUploadDialog(_BaseUploadDialog):

    def __init__(self, api: TestKit, hid: HID):
        _custom_upload_dialog_locator = {
            "name": "QFileDialog",
            "type": "QnCustomFileDialog",
            "visible": 1,
            }
        super().__init__(api=api, hid=hid, dialog_locator=_custom_upload_dialog_locator)
