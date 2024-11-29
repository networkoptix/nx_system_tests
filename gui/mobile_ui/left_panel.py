# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection

from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID


class LeftPanel:

    def __init__(self, api: TestKit, hid: HID):
        # TODO: Add the id for this panel and use it instead of cloud panel.
        #  See: SideNavigation.qml file
        self._api = api
        self._hid = hid

    def disconnect_from_server(self):
        _logger.info('%r: Disconnect from server', self)
        button_widget_locator = {
            'id': 'disconnectButton',
            'text': 'Disconnect from Server',
            'visible': True,
            'enabled': True,
            }
        button = Button(Widget(self._api, button_widget_locator))
        self._hid.mouse_left_click_on_object(button)
        self.wait_for_inaccessible()

    def get_cloud_panel(self) -> '_CloudPanel':
        return _CloudPanel(Widget(self._api, {
            'visible': True,
            'enabled': True,
            'type': 'CloudPanel',
            }))

    def _get_resources_widget(self) -> '_ResourcesWidget':
        return _ResourcesWidget(Widget(self._api, {
            'id': 'layoutsList',
            'type': 'QQuickListView',
            'visible': True,
            'enabled': True,
            }))

    def get_layout_nodes(self) -> Collection['_LayoutNode']:
        return self._get_resources_widget().get_layouts()

    def wait_for_inaccessible(self):
        self.get_cloud_panel().wait_for_inaccessible()

    def get_layout(self, layout_name: str) -> '_LayoutNode':
        for layout in self.get_layout_nodes():
            if layout.name() == layout_name:
                return layout
        raise RuntimeError(f'Layout {layout_name!r} not found in left panel')

    def open_layout(self, layout_name: str):
        _logger.info('%r: Open layout "%s"', self, layout_name)
        layout = self.get_layout(layout_name)
        self._hid.mouse_left_click(layout.bounds().center())

    def get_active_layout(self) -> '_LayoutNode':
        active_layouts = [layout for layout in self.get_layout_nodes() if layout.is_active()]
        try:
            [active_layout] = active_layouts
        except ValueError:
            raise RuntimeError(
                f"Exactly one layout has to be active at a time. "
                f"Active layouts count: {len(active_layouts)}",
                )
        return active_layout


class _CloudPanel:

    def __init__(self, widget: Widget):
        self._widget = widget

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def wait_for_inaccessible(self):
        self._widget.wait_for_inaccessible()

    def wait_for_accessible(self, timeout: float = 1):
        self._widget.wait_for_accessible(timeout)


class _ResourcesWidget:

    def __init__(self, widget: Widget):
        self._widget = widget

    def get_layouts(self) -> Collection['_LayoutNode']:
        widgets = self._widget.find_children({'type': 'LayoutItem', 'visible': True})
        return [_LayoutNode(widget) for widget in widgets]


class _LayoutNode:

    def __init__(self, widget: Widget):
        self._widget = widget

    def name(self) -> str:
        return self._widget.get_text()

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def get_resource_count(self) -> int:
        label = self._widget.find_child({'visible': True, 'id': 'countLabel'})
        return int(label.get_text())

    def is_active(self) -> bool:
        return self._widget.wait_property('active')


_logger = logging.getLogger(__name__)
