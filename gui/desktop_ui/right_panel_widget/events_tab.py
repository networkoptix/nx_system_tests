# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Collection

from gui.desktop_ui.right_panel_widget.base_tab import _RightPanelTab
from gui.testkit import TestKit

_logger = logging.getLogger(__name__)


class _EventsTab(_RightPanelTab):

    def __init__(self, api: TestKit):
        super().__init__(api, {
            "name": "AbstractSearchWidget",
            "type": "nx::vms::client::desktop::EventsSearchWidget",
            "visible": 1,
            })

    def get_event_names(self) -> Collection[str]:
        tile_names = []
        for tile in self.tile_loaders():
            label = tile.find_child({
                "name": "nameLabel",
                "type": "QLabel",
                "visible": 1,
                })
            search_result = re.search(r'(?<=>)([\w\s]+)(?=</)', label.get_text())
            text = label.get_text() if search_result is None else search_result.group(0)
            tile_names.append(text)
        return tile_names
