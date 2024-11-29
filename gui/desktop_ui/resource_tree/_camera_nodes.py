# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CameraNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in camera node: {self._data}")

    @classmethod
    def is_camera_node(cls, model):
        return model['icon'] in (
            cls._icons.CameraRecording.value,
            cls._icons.CameraOnline.value,
            cls._icons.CameraOffline.value,
            cls._icons.VirtualCamera.value,
            )

    def is_offline(self):
        return self._data['icon'] == self._icons.CameraOffline.value

    def is_recording(self):
        recording_state = self._object.find_child({'enabled': 'True', 'id': 'recordingIcon'})
        if recording_state.wait_property('source'):
            return True
        return False

    def open(self) -> CameraSceneItem:
        _logger.info('Open camera %s by double click', self.name)
        self._double_click()
        item = CameraSceneItem(self._api, self._hid, self.name)
        # Scene item opens with a delay after node double click and exceeds 3 seconds default.
        item.wait_for_accessible(timeout=6)
        return item

    def open_in_new_tab(self) -> CameraSceneItem:
        _logger.info('Open camera %s in new tab', self.name)
        self._open_context_menu()
        menu = QMenu(self._api, self._hid)
        menu_options = menu.get_options()
        deprecated_option_name = 'Open in New Tab'  # VMS 6.0.
        option_name = 'Open in'  # VMS 6.1 and higher.
        if deprecated_option_name in menu_options:
            menu.activate_items(deprecated_option_name)
        else:
            menu.activate_items(option_name, 'New Tab')
        return CameraSceneItem(self._api, self._hid, self.name)

    def drag_n_drop_on_scene(self) -> CameraSceneItem:
        super().drag_n_drop_on_scene()
        return CameraSceneItem(self._api, self._hid, self.name)

    def open_by_context_menu(self):
        _logger.info('Open camera %s by context menu', self.name)
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items("Open")
        time.sleep(.5)

    def open_settings_multiple_cameras(self) -> CameraSettingsDialog:
        _logger.info('Open Cameras Settings Dialog for multiple cameras')
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items("Cameras Settings...")
        return CameraSettingsDialog(self._api, self._hid).wait_until_appears()

    def open_settings(self) -> CameraSettingsDialog:
        _logger.info('Open Camera Settings Dialog for camera %s', self.name)
        self._activate_context_menu_item("Camera Settings...")
        return CameraSettingsDialog(self._api, self._hid).wait_until_appears()

    def open_upload_file_dialog(self) -> UploadDialog:
        _logger.info('Open Upload File Dialog for camera %s', self.name)
        self._activate_context_menu_item('Upload File...')
        return UploadDialog(self._api, self._hid).wait_until_appears()

    def open_upload_folder_dialog(self) -> UploadDialog:
        _logger.info('Open Upload Folder Dialog for camera %s', self.name)
        self._activate_context_menu_item('Upload Folder...')
        return UploadDialog(self._api, self._hid).wait_until_appears()

    def start_removing(self):
        _logger.info('Start removing camera %s', self.name)
        self._activate_context_menu_item("Delete")

    def remove_from_layout(self):
        _logger.info('Remove camera %s from layout', self.name)
        self._activate_context_menu_item("Remove from Layout")

    def move_to_server(self, target):
        self.drag_n_drop(target)
        # Sometimes we get a message box here, for example when moving a testcamera.
        button = MessageBox(self._api, self._hid).get_button_with_text("Move")
        if button.is_accessible_timeout(1):
            _logger.info('Confirm moving to another server')
            self._hid.mouse_left_click_on_object(button)

    def _set_group_name(self, name):
        # New group must be expanded and editable after creation.
        if name:
            self.get_name_editor().type_text(name)
        self._hid.keyboard_hotkeys('Return')
        time.sleep(1)

    def create_group(self, use_hotkey=False, name=None):
        _logger.info('Create group from camera %s', self.name)
        if use_hotkey:
            self._hid.keyboard_hotkeys('Ctrl', 'G')
            self._set_group_name(name)
        else:
            self._activate_context_menu_item('Create Group')
            self._set_group_name(name)

    def is_creation_group_available(self):
        menu = QMenu(self._api, self._hid)
        if menu.is_accessible():
            menu.close()
        self._open_context_menu()
        return menu.get_options()['Create Group'].enabled

    def cancel_renaming(self, new_name: str):
        _logger.info('Start renaming camera %s and cancel', self.name)
        self.click()
        self._hid.keyboard_hotkeys('F2')
        time.sleep(1)
        self.get_name_editor().type_text(new_name)
        self._hid.keyboard_hotkeys('Escape')
        time.sleep(1)
