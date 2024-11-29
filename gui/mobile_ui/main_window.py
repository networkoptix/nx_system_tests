# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.widget import Widget
from gui.testkit import TestKit


class MainWindow:

    def __init__(self, testkit_api: TestKit):
        self._widget = Widget(testkit_api, {'id': 'mainWindow', 'visible': True})

    def set_position(self, x: int, y: int):
        _logger.info('Set Main Window position {x: %s, y: %s}', x, y)
        self._widget.set_attribute_value('x', x)
        self._widget.set_attribute_value('y', y)


_logger = logging.getLogger(__name__)
