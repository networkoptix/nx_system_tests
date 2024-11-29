# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui import testkit
from gui.desktop_ui.dialogs.connect_to_server import ConnectToServerDialog
from gui.desktop_ui.dialogs.disconnect_from_mediaserver import DisconnectFromMediaserverDialog
from gui.desktop_ui.dialogs.edit_webpage import EditIntegration
from gui.desktop_ui.dialogs.edit_webpage import EditWebPageDialog
from gui.desktop_ui.dialogs.local_settings import LocalSettingsDialog
from gui.desktop_ui.dialogs.new_virtual_camera import NewVirtualCameraDialog
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.dialogs.user_management import UserManagementWidget
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class MainMenu:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = QMenu(api, hid)
        self._title_bar = Widget(api, {
            "type": "QnMainWindowTitleBarWidget",
            "visible": 1,
            })

    def _open(self):
        if not self._obj.is_accessible_timeout(0.5):
            button = self._title_bar.find_child({
                "text": "Main Menu",
                "type": "nx::vms::client::desktop::ToolButton",
                "unnamed": 1,
                "visible": 1,
                })
            self._hid.mouse_left_click_on_object(button)
        if not self._obj.is_accessible_timeout(5):
            raise RuntimeError("Main menu is not open")

    def activate_items_de(self, *args, **kwargs):
        german_button = Widget(self._api, {
            "type": "nx::vms::client::desktop::ToolButton",
            "unnamed": 1,
            "visible": 1,
            "text": "Hauptmenü",
            })
        self._hid.mouse_left_click_on_object(german_button)
        self._obj.activate_items(*args, **kwargs)

    def activate_items(self, *args, **kwargs):
        self._open()
        self._obj.activate_items(*args, **kwargs)

    def open_file(self, path):
        _logger.info('%r: Open files %s', self, path)
        self.activate_items('Open', 'Files...')
        dialog = UploadDialog(self._api, self._hid)
        dialog.wait_for_accessible()
        dialog.upload_file(str(path))

    def activate_new_virtual_camera(self) -> NewVirtualCameraDialog:
        _logger.info('%r: Open Virtual Camera Dialog', self)
        self._open()
        self._obj.activate_items('Add', 'Virtual Camera...')
        return NewVirtualCameraDialog(self._api, self._hid).wait_until_appears()

    def activate_connect_to_server(self) -> ConnectToServerDialog:
        _logger.info('%r: Open Connect to Server Dialog', self)
        try:
            self.activate_items('Connect to Server...')
        except testkit.ObjectNotFound:
            self.activate_items('Connect to Another Server...')
        return ConnectToServerDialog(self._api, self._hid)

    def activate_browse_local_files(self):
        _logger.info('%r: Open Browse Local Files Dialog', self)
        self.activate_items('Browse Local Files')

    def activate_audit_trail(self):
        _logger.info('%r: Open Audit Trail Dialog', self)
        self.activate_items('Audit Trail...')

    def activate_new_showreel(self):
        _logger.info('%r: Open Showreel Dialog', self)
        self._open()
        self._obj.activate_items('Add', 'Showreel...')

    def activate_merge_systems(self):
        _logger.info('%r: Open Merge Systems(Sites) Dialog', self)
        self.activate_items(re.compile('Merge (Systems|Sites)...'))

    def activate_system_administration(self) -> SystemAdministrationDialog:
        _logger.info('%r: Open System(Site) Administration Dialog', self)
        self.activate_items(re.compile('(System|Site) Administration...'))
        return SystemAdministrationDialog(self._api, self._hid)

    def has_new_webpage(self) -> bool:
        # TODO: Make it via object lookup
        return self.activate_new_webpage().is_accessible()

    def activate_new_webpage(self) -> EditWebPageDialog:
        _logger.info('%r: Open New Web Page Dialog', self)
        self._open()
        self._obj.activate_items('Add', 'Web Page...')
        return EditWebPageDialog(self._api, self._hid).wait_until_appears()

    def activate_new_integration(self) -> EditIntegration:
        _logger.info('%r: Open New Integration Dialog', self)
        self._open()
        self._obj.activate_items('Add', 'Integration...')
        return EditIntegration(self._api, self._hid).wait_until_appears()

    def activate_new_videowall(self):
        _logger.info('%r: Open New Video Wall Dialog', self)
        self._open()
        self._obj.activate_items('Add', 'Video Wall...')

    def activate_user_management(self) -> UserManagementWidget:
        _logger.info('%r: Open User Management Dialog', self)
        self.activate_items('User Management...')
        dialog = SystemAdministrationDialog(self._api, self._hid)
        dialog.wait_for_accessible()
        return UserManagementWidget(self._api, self._hid)

    def disconnect_from_server(self):
        _logger.info('%r: Disconnect from server', self)
        self.activate_items('Disconnect from Server')
        disconnect_dialog = DisconnectFromMediaserverDialog(self._api, self._hid)
        if disconnect_dialog.is_shown():
            disconnect_dialog.click_disconnect()

    def open_local_settings_dialog(self) -> LocalSettingsDialog:
        _logger.info('%r: Open Local Settings Dialog', self)
        self.activate_items('Local Settings...')
        return LocalSettingsDialog(self._api, self._hid).wait_until_appears()

    def has_save_window_configuration(self):
        self._open()
        return 'Save Windows Configuration' in self._obj.get_options()

    def activate_save_window_configuration(self):
        _logger.info('%r: Save window configuration', self)
        self.activate_items('Save Windows Configuration')
