# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import date
from datetime import datetime
from typing import List
from typing import Sequence

from gui.desktop_ui.dialogs.camera_selection import CameraSelectionDialog
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTable
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)
_date_format = '%m/%d/%Y'


class BookmarksLog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._window = BaseWindow(api=api, locator_or_obj={
            "name": "BookmarksLog",
            "type": "QnDialog",
            "visible": 1,
            "occurrence": 1,
            })

    def get_table(self):
        table_object = self._window.find_child({
            "name": "gridBookmarks",
            "visible": 1,
            })
        return QTable(self._hid, table_object, ['name', 'camera', 'start_time', 'length', 'created', 'creator', 'tags'])

    def is_open(self):
        return self._window.is_open()

    def open_using_hotkey(self):
        _logger.info('%r: Open by hot key', self)
        self._hid.keyboard_hotkeys('Ctrl', 'B')
        self._window.wait_for_accessible()
        return self

    def close(self):
        _logger.info('%r: Close', self)
        self._window.close()

    def filter_by_text(self, text: str):
        _logger.info('%r: Filter by text: %s', self, text)
        self._get_search_field().set_text_without_validation(text)

    def current_text_filter(self):
        return self._get_search_field().get_text()

    def _get_search_field(self):
        return QLineEdit(self._hid, self._window.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            }))

    def filter_by_cameras(self, camera_names: List[str]):
        _logger.info('BookmarksLog: Filter by cameras: %s', camera_names)
        devices_button = Button(self._window.find_child({
            "name": "cameraButton",
            "type": "QnSelectDevicesButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(devices_button)
        camera_selection_dialog = CameraSelectionDialog(self._api, self._hid)
        camera_selection_dialog.select_cameras(camera_names)
        camera_selection_dialog.save()

    def filter_by_period(self, start: date = None, end: date = None):
        _logger.info('BookmarksLog: Filter by period: start %s, end %s', start, end)
        if start:
            start = start.strftime(_date_format)
            date_edit_from_object = self._window.find_child({
                "name": "dateEditFrom",
                "type": "QDateEdit",
                "visible": 1,
                })
            start_date_field = QLineEdit(self._hid, date_edit_from_object.find_child({
                "name": "qt_spinbox_lineedit",
                "type": "QLineEdit",
                "visible": 1,
                }))
            start_date_field.set_text_without_validation(start)
        if end:
            end = end.strftime(_date_format)
            date_edit_to_locator = self._window.find_child({
                "name": "dateEditTo",
                "type": "QDateEdit",
                "visible": 1,
                })
            finish_date_field = QLineEdit(self._hid, date_edit_to_locator.find_child({
                "name": "qt_spinbox_lineedit",
                "type": "QLineEdit",
                "visible": 1,
                }))
            finish_date_field.set_text_without_validation(end)
        time.sleep(1)

    def clear(self):
        _logger.info('%r: Clear', self)
        clear_filter_button = Button(self._window.find_child({
            "name": "clearFilterButton",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(clear_filter_button)
        time.sleep(1)
        # This resets the date only to one year before now, which is not enough for our cases,
        # so we reset it manually to the lowest possible value.
        self.filter_by_period(date(day=1, month=1, year=2000))

    def bookmark_by_name(self, name) -> '_Bookmark':
        _logger.info('%r: Looking for bookmark with name %s', self, name)
        for b in self.all_bookmarks():
            if b.name() == name:
                return b
        raise RuntimeError(f"No bookmark with name {name}")

    def all_bookmarks(self) -> Sequence['_Bookmark']:
        return [_Bookmark(row) for row in self.get_table().all_rows()]

    def wait_for_bookmarks_quantity(self, quantity: int, timeout: float = 10):
        _logger.info(
            '%r: Wait for there are %s bookmarks. Timeout: %s second(s)',
            self, quantity, timeout)
        refresh_button = self._window.find_child({'text': 'Refresh', 'type': 'QPushButton'})
        start_time = time.monotonic()
        while True:
            if len(self.all_bookmarks()) == quantity:
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(
                    f"Incorrect quantity of bookmarks."
                    f"Expected {quantity}, got {len(self.all_bookmarks())}.")
            time.sleep(.5)
            self._hid.mouse_left_click_on_object(refresh_button)

    def order_by(self, column):
        _logger.info('%r: Order by column: %s', self, column)
        self.get_table().click_header(column)


class _Bookmark:

    def __init__(self, row):
        self._row = row

    def name(self):
        return self._row.cell('name').get_display_text()

    def camera(self):
        return self._row.cell('camera').get_display_text()

    def tags(self):
        return self._row.cell('tags').get_display_text()

    def length(self):
        return self._row.cell('length').get_display_text()

    def start_time(self):
        text = self._row.cell('start_time').get_display_text()
        return datetime.strptime(text, f'{_date_format} %I:%M:%S %p')

    def context_menu(self, item):
        self._row.cell('name').context_menu(item)
