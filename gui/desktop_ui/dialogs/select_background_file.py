# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Collection

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class FileDialogError(Exception):
    pass


class BackgroundFileDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def __repr__(self):
        return '<BackgroundFileDialog>'

    def _get_container(self):
        """Get a container of file dialog.

        This method is required as a currently used container type depends
        on the user's filesystem display settings.
        """
        dialog = BaseWindow(api=self._api, locator_or_obj={
            "name": "LayoutSettingsDialog",
            "type": "nx::vms::client::desktop::LayoutSettingsDialog",
            "visible": 1,
            "occurrence": 1,
            })
        background_settings = dialog.find_child({
            "name": "LayoutBackgroundSettingsWidget",
            "type": "nx::vms::client::desktop::LayoutBackgroundSettingsWidget",
            "visible": 1,
            })
        list_view = background_settings.find_child({
                "name": "listView",
                "type": "QListView",
                "visible": 1,
                })
        if list_view.is_accessible_timeout(0.5):
            return list_view
        _logger.info("Current container is not a QListView")
        tree_view = background_settings.find_child({
                "name": "treeView",
                "type": "QTreeView",
                "visible": 1,
                })
        if tree_view.is_accessible_timeout(0.5):
            return tree_view
        _logger.info("Current container is not a QTreeView")
        raise FileDialogError("Unknown container in file dialog")

    def _file_list(self) -> Collection['Widget']:
        return self._get_container().find_children({
            'type': 'QModelIndex',
            'column': 0,
            })

    def _file(self, filename: str):
        _logger.info('%r: Looking for file %s', self, filename)
        for file in self._file_list():
            if file.get_text() == filename:
                return file
        raise FileDialogError(f"File {filename} not found in directory.")

    def filenames(self):
        return [file.get_text() for file in self._file_list()]

    def double_click_file(self, name):
        _logger.info('%r: Double click file %s', self, name)
        self._hid.mouse_double_click_on_object(self._file(name))

    def wait_until_closed(self, timeout: float = 5):
        _logger.debug('Waiting for object %r inaccessible. Timeout %s second(s)', self, timeout)
        start_time = time.monotonic()
        while True:
            try:
                self._get_container()
            except FileDialogError:
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"Timed Out: Object {self!r} is accessible within timeout: {timeout}")
            time.sleep(.1)
