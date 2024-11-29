# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.widget import WidgetIsNotAccessible
from gui.desktop_ui.wrappers import Button
from gui.mobile_ui.left_panel import LeftPanel
from gui.testkit import TestKit
from gui.testkit.hid import HID


class ApplicationWindow:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._widget = Widget(api, {'name': 'ApplicationWindow', 'visible': True})
        self._hid = hid

    def open_left_panel_widget(self) -> LeftPanel:
        _logger.info('%r: Open left panel widget', self)
        button = self._widget.find_child({'id': 'leftButton', 'visible': True})
        attempt_count = 3
        for _attempt in range(attempt_count):
            self._hid.mouse_left_click(button.center())
            try:
                return self._get_left_panel_widget_within_timeout()
            except WidgetIsNotAccessible:
                _logger.info('Left panel is not accessible after click. Retry')
        raise RuntimeError(f'Left panel is not accessible after {attempt_count} clicks')

    def _get_left_panel_widget_within_timeout(self):
        window_bounds = self._widget.bounds()
        left_panel = LeftPanel(self._api, self._hid)
        cloud_panel = left_panel.get_cloud_panel()
        cloud_panel.wait_for_accessible()
        started_at = time.monotonic()
        while True:
            if window_bounds.contains_rectangle(cloud_panel.bounds()):
                _logger.debug('%r: Left panel is ready for interaction', self)
                return left_panel
            if time.monotonic() - started_at > 1:
                raise RuntimeError('Left panel is not ready within timeout')
            _logger.info('%r: Left panel is not ready for interaction', self)
            time.sleep(0.1)

    def close_left_panel(self):
        _logger.info('%r: Close Left Panel', self)
        left_panel = self._get_left_panel_widget_within_timeout()
        self._hid.mouse_left_click(self._widget.bounds().middle_right().left(30))
        left_panel.wait_for_inaccessible()

    def navigate_back(self):
        _logger.info('%r: Navigate back', self)
        button = Button(Widget(self._api, {
            'id': 'leftButton',
            'type': 'IconButton',
            'visible': True,
            'enabled': True,
            }))
        self._hid.mouse_left_click_on_object(button)


_logger = logging.getLogger(__name__)
