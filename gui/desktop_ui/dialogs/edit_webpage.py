# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.messages import WebPageCertificateDialog
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMenu
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class EditWebPageDialog(BaseWindow):

    def __init__(self, api: TestKit, hid: HID):
        super(EditWebPageDialog, self).__init__(api=api, locator_or_obj={
            "name": "WebpageDialog",
            "type": "nx::vms::client::desktop::QnWebpageDialog",
            "visible": 1,
            })
        self._hid = hid
        self._current_open_tab_name = None

    def _get_line_edit_by_left_label(self, label: str) -> QLineEdit:
        label_locator = {
            "text": label,
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            }
        line_edit = self.find_child({
            "leftWidget": label_locator,
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        return QLineEdit(self._hid, line_edit)

    def get_url(self) -> str:
        self.switch_tab('General')
        return self._get_line_edit_by_left_label('URL').get_text()

    def get_name(self) -> str:
        self.switch_tab('General')
        return self._get_line_edit_by_left_label('Name').get_text()

    def get_proxy_via_server_checkbox(self):
        checkbox = self.find_child({
            "name": "proxyViaServerCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def get_proxy_via_server(self) -> bool:
        self.switch_tab('General')
        return self.get_proxy_via_server_checkbox().is_checked()

    def switch_tab(self, tab_name):
        if self._current_open_tab_name != tab_name:
            _logger.info('%r: Set tab %s', self, tab_name)
            tab_bar = self.find_child({
                "name": "qt_tabwidget_tabbar",
                "type": "QTabBar",
                "visible": 1,
                })
            tab = TabWidget(tab_bar).find_tab(tab_name)
            self._hid.mouse_left_click_on_object(tab)
            self._current_open_tab_name = tab_name

    def get_proxy_all_content_checkbox(self):
        self.switch_tab('Advanced')
        proxy_all_checkbox = self.find_child({
            "name": "proxyAllContentsCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, proxy_all_checkbox)

    def proxy_all_content_is_enabled(self) -> bool:
        return self.get_proxy_all_content_checkbox().is_enabled()

    def get_disable_sll_checkbox(self):
        self.switch_tab('Advanced')
        proxy_all_checkbox = self.find_child({
            "name": "disableCertificateCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, proxy_all_checkbox)

    def create_proxied_resource(
            self,
            url,
            name,
            proxy_server_name,
            proxy_all=None,
            ) -> WebPageSceneItem:
        _logger.info(
            '%r: Create proxied resource. '
            'Url %s, name %s, proxy server name %s, Proxy All checkbox value %s',
            self, url, name, proxy_server_name, proxy_all)
        self.switch_tab('General')
        self._set_url(url)
        self.set_name(name)
        self.set_proxy_via_server(True)
        self.set_proxy_server(proxy_server_name)
        if proxy_all is not None:
            self.get_proxy_all_content_checkbox().set(proxy_all)
        self.save_and_close()
        return WebPageSceneItem(self._api, self._hid, name)

    def create_resource(self, url, name) -> WebPageSceneItem:
        _logger.info('%r: Create resource with url %s name %s', self, url, name)
        self.switch_tab('General')
        self._set_url(url)
        self.set_name(name)
        self.save_and_close()
        return WebPageSceneItem(self._api, self._hid, name)

    def _get_proxy_server_button(self):
        button = self.find_child({
            "name": "selectServerMenuButton",
            "type": "QnChooseServerButton",
            "visible": 1,
            })
        return Button(button)

    def _proxy_server_button_is_accessible(self) -> bool:
        return self._get_proxy_server_button().is_accessible_timeout(0.5)

    def create_proxied_resource_over_single_server(self, url, name) -> WebPageSceneItem:
        _logger.info(
            '%r: Create proxied web page over single server with url %s name %s',
            self, url, name)
        self.switch_tab('General')
        self._set_url(url)
        self.set_name(name)
        self.set_proxy_via_server(True)
        if self._proxy_server_button_is_accessible():
            raise RuntimeError(
                "More than one server in the system. "
                "Use this method only for systems containing one server.")
        self.save_and_close()
        return WebPageSceneItem(self._api, self._hid, name)

    def _set_url(self, value):
        self._get_line_edit_by_left_label('URL').type_text(value)

    def set_name(self, value):
        _logger.info('%r: Set web page name to %s', self, value)
        self.switch_tab('General')
        self._get_line_edit_by_left_label('Name').type_text(value)

    def set_proxy_via_server(self, value):
        _logger.info('%r: Set proxy via server checkbox value to %s', self, value)
        self.switch_tab('General')
        self.get_proxy_via_server_checkbox().set(value)

    def set_proxy_server(self, server_name):
        _logger.info('%r: Set proxy server to %s', self, server_name)
        self.switch_tab('General')
        self._hid.mouse_left_click_on_object(self._get_proxy_server_button())
        menu = QMenu(self._api, self._hid)
        menu_item = [
            item for item in menu.get_options()
            if server_name in item
            ]
        if len(menu_item) != 1:
            raise RuntimeError(f"Found several menu items for server {server_name} in proxy menu")
        menu.activate_items(menu_item[0])

    def _get_ok_button(self):
        button = self.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(button)

    def try_save(self):
        _logger.info('%r: Try save', self)
        self._hid.mouse_left_click_on_object(self._get_ok_button())

    def save_and_close(self):
        _logger.info('%r: Save and close', self)
        self._hid.mouse_left_click_on_object(self._get_ok_button())
        self.wait_until_closed()


def suppress_connect_anyway(api: TestKit, hid: HID, timeout_sec: float = 20):
    # Sometimes 'Connect Anyway' MessageBox appears, sometimes not
    # This depends on VM and web-site
    start_time = time.monotonic()
    while True:
        # Maintain the old version of dialog.
        if (webpage_confirmation := MessageBox(api, hid)).is_accessible_timeout(0.5):
            _logger.info('Accept "Connect Anyway" Message Box warning')
            webpage_confirmation.close_by_button("Connect anyway")
            return
        if (webpage_confirmation := WebPageCertificateDialog(api, hid)).is_accessible_timeout(0.5):
            _logger.info('Accept "Connect Anyway" WebPageCertificateDialog warning')
            webpage_confirmation.connect_anyway()
            return
        if time.monotonic() - start_time > timeout_sec:
            _logger.info('No "Connect Anyway" Message Box appeared within timout')
            return
        time.sleep(.1)


class EditIntegration(EditWebPageDialog):

    def __init__(self, api, hid):
        super().__init__(api=api, hid=hid)

    def get_warning_text(self):
        warning_label = self.find_child({
            'visible': True,
            'acceptDrops': False,
            'type': 'QnWordWrappedLabel',
            })
        return QLabel(warning_label).get_text()
