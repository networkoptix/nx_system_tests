# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui.desktop_ui.right_panel_widget.base_tab import _RightPanelTab
from gui.desktop_ui.right_panel_widget.base_tab import _remove_html_tags
from gui.desktop_ui.wrappers import QLabel
from gui.testkit import TestKit

_logger = logging.getLogger(__name__)


class _MotionTab(_RightPanelTab):

    def __init__(self, api: TestKit):
        super().__init__(api, {
            "name": "AbstractSearchWidget",
            "type": "nx::vms::client::desktop::SimpleMotionSearchWidget",
            "visible": 1,
            })

    def camera_filter_value(self):
        selector = self._ribbon.find_child({
            "type": "nx::vms::client::desktop::SelectableTextButton",
            "visible": 1,
            'text': re.compile('^Selected camera.*'),
            })
        return QLabel(selector).get_text()

    def has_events_for(self, camera_name):
        _logger.info('%r: Looking for event for camera %s', self, camera_name)
        for tile_loader in self.tile_loaders():
            name_label = tile_loader.find_child({
                "name": "resourceListLabel",
                "type": "QLabel",
                "visible": 1,
                })
            # Text is enclosed in <b> tag =(.
            if _remove_html_tags(name_label.get_text()) == camera_name:
                return True
        return False
