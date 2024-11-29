# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time

from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMLComboBoxIncremental
from gui.desktop_ui.wrappers import QSpinBox
from gui.desktop_ui.wrappers import SwitchIcon
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CameraSettingsDialog(BaseWindow):

    def __init__(self, api: TestKit, hid: HID):
        dialog_locator = {
            "name": "CameraSettingsDialog",
            "type": "nx::vms::client::desktop::CameraSettingsDialog",
            "visible": 1,
            "occurrence": 1,
            }

        super().__init__(api=api, locator_or_obj=dialog_locator)
        self.general_tab = _GeneralTab(dialog_locator, api=api, hid=hid)
        self.recording_tab = _RecordingTab(dialog_locator, api=api, hid=hid)
        self.motion_tab = _MotionTab(dialog_locator, api=api, hid=hid)
        self.dewarping_tab = _DewarpingTab(dialog_locator, api=api, hid=hid)
        self.expert_tab = _ExpertTab(dialog_locator, api=api, hid=hid)
        self.plugins_tab = _PluginsTab(dialog_locator, api=api, hid=hid)
        self._api = api
        self._hid = hid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # If an exception not occurred - need to close dialog
        # Otherwise re-raise the exception.
        if exc_type is None:
            self.close()

    def activate_tab(self, tab_name):
        _logger.info('%r: Activate tab %s', self, tab_name)
        tab_widget = self.find_child({
            "name": "qt_tabwidget_tabbar",
            "type": "QTabBar",
            "visible": 1,
            })
        tab = TabWidget(tab_widget).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)
        time.sleep(1)

    def activate_integrations_tab(self):
        # TODO: Keep only "Integrations" when 6.0 and older versions are abandoned.
        self.activate_tab(re.compile('Plugins|Integrations'))

    def get_apply_button(self) -> Button:
        return Button(self.find_child({
            "text": "Apply",
            "visible": 1,
            }))

    def apply_changes(self):
        apply_button = self.get_apply_button()
        self._hid.mouse_left_click_on_object(apply_button)

    def close(self):
        ok_button = self.find_child({
            "text": "OK",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self.wait_until_closed()

    def save_changes(self):
        _logger.info('%r: Save and close', self)
        self.close()

    def enable_recording(self):
        _logger.info('%r: Enable recording', self)
        self.activate_tab('Recording')
        self.recording_tab.set_enabled(True)
        self.close()

    def start_recording(self):
        _logger.info('%r: Start recording', self)
        self.activate_tab('Recording')
        self.recording_tab.set_enabled(True)
        self.recording_tab.set_record_always_schedule()
        self.recording_tab.set_schedule('always')
        self.close()

    def stop_recording(self):
        _logger.info('%r: Stop recording', self)
        self.activate_tab('Recording')
        self.recording_tab.set_enabled(False)
        self.close()

    def upload_file(self, path):
        _logger.info('%r: Upload file: %s', self, path)
        self.general_tab.open_upload_file_dialog().upload_file(
            str(path),
            time_sleep=20)
        assert self.general_tab.wait_for_upload_button_accessible()
        time.sleep(1)
        self.close()


class _BaseTab:

    def __init__(self, dialog_locator, api):
        self._tab_widget_locator = {
            "name": "qt_tabwidget_stackedwidget",
            "type": "QStackedWidget",
            "visible": 1,
            "window": dialog_locator}
        self._dialog = BaseWindow(api, dialog_locator)


class _GeneralTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._api = api
        self._hid = hid

    def _get_tab_overlay(self):
        return self._dialog.find_child({
            "name": "CameraSettingsGeneralTabWidget",
            "type": "nx::vms::client::desktop::CameraSettingsGeneralTabWidget",
            "visible": 1,
            })

    def _get_image_rotation_combobox(self):
        combobox = self._dialog.find_child({
            "name": "rotationComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, combobox)

    def get_image_rotation(self) -> str:
        return self._get_image_rotation_combobox().current_item()

    def _get_min_keep_archive_field(self):
        field = self._get_tab_overlay().find_child({
            "name": "qt_spinbox_lineedit",
            "type": "QLineEdit",
            "visible": 1,
            "occurrence": 1,
            })
        return QLineEdit(self._hid, field)

    def get_min_keep_archive(self) -> str:
        return self._get_min_keep_archive_field().get_text()

    def get_min_keep_archive_unit(self) -> str:
        min_keep_archive_unit_combobox = self._get_tab_overlay().find_child({
            "name": "comboBoxMinPeriodUnit",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, min_keep_archive_unit_combobox).current_item()

    def _get_max_keep_archive_field(self):
        field = self._get_tab_overlay().find_child({
            "name": "qt_spinbox_lineedit",
            "type": "QLineEdit",
            "visible": 1,
            "occurrence": 2,
            })
        return QLineEdit(self._hid, field)

    def get_max_keep_archive(self) -> str:
        return self._get_max_keep_archive_field().get_text()

    def get_max_keep_archive_unit(self) -> str:
        max_keep_archive_unit_combobox = self._get_tab_overlay().find_child({
            "name": "comboBoxMaxPeriodUnit",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, max_keep_archive_unit_combobox).current_item()

    def get_ignore_time_zone_check_box(self):
        checkbox = self._get_tab_overlay().find_child({
            "name": "ignoreTimeZoneCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def get_ignore_time_zone(self) -> bool:
        return self.get_ignore_time_zone_check_box().is_checked()

    def _get_detect_motion_checkbox(self):
        checkbox = self._get_tab_overlay().find_child({
            "name": "motionDetectionCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def _get_detection_sensitivity_combo_box(self):
        combobox = self._get_tab_overlay().find_child({
            "name": "sensitivityComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, combobox)

    def get_detection_sensitivity(self):
        if self._get_detect_motion_checkbox().is_checked():
            return self._get_detection_sensitivity_combo_box().current_item()
        return None

    def set_image_rotation(self, degree):
        _logger.info('%r: Set image rotation: %s degrees', self, degree)
        self._get_image_rotation_combobox().select(f"{degree} degrees")

    def _get_aspect_ratio_combo_box(self):
        combobox = self._get_tab_overlay().find_child({
            "name": "aspectRatioComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, combobox)

    def set_aspect_ratio(self, value: str):
        _logger.info('%r: Set aspect ratio: %s', self, value)
        self._get_aspect_ratio_combo_box().select(value)

    def _aspect_ratio_is_accessible(self) -> bool:
        return self._get_aspect_ratio_combo_box().is_accessible_timeout(0.5)

    def reset_image_controls(self):
        _logger.info('%r: Reset image controls', self)
        self.set_image_rotation(0)
        if self._aspect_ratio_is_accessible():
            self.set_aspect_ratio('Auto')

    def _get_min_keep_archive_check_box(self):
        checkbox = self._get_tab_overlay().find_child({
            "name": "checkBoxMinArchive",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def set_auto_min_keep_archive(self, value: bool):
        _logger.info(
            '%r: Set Auto min keep archive to %s',
            self, value)
        self._get_min_keep_archive_check_box().set(value)

    def set_min_keep_archive(self, days: int = None):
        _logger.info('%r: Set keeping archive minimum for %s day(s)', self, days)
        self._get_min_keep_archive_check_box().set(False)
        if days is not None:
            self._get_min_keep_archive_field().type_text(str(days))

    def get_max_keep_archive_auto_check_box(self):
        checkbox = self._get_tab_overlay().find_child({
            "name": "checkBoxMaxArchive",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def set_auto_max_keep_archive(self, value):
        _logger.info(
            '%r: Set Auto max keep archive to %s',
            self, value)
        self.get_max_keep_archive_auto_check_box().set(value)

    def set_max_keep_archive(self, days: int = None):
        _logger.info('%r: Set keeping archive maximum for %s day(s)', self, days)
        self.get_max_keep_archive_auto_check_box().set(False)
        if days is not None:
            self._get_max_keep_archive_field().type_text(str(days))

    def set_ignore_time_zone(self, value):
        _logger.info('%r: Set ignore time zone', self)
        self.get_ignore_time_zone_check_box().set(value)

    def set_detection_sensitivity(self, sensitivity: int = None):
        _logger.info('%r: Turn on motion detection', self)
        self._get_detect_motion_checkbox().set(True)
        if sensitivity is not None:
            _logger.info('%r: Set detection sensitivity to %s', self, sensitivity)
            self._get_detection_sensitivity_combo_box().select(str(sensitivity))

    def _get_upload_file_button(self):
        button = self._get_tab_overlay().find_child({
            "name": "uploadFileButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def wait_for_upload_button_accessible(self):
        self._get_upload_file_button().wait_for_accessible(20)

    def open_upload_file_dialog(self) -> UploadDialog:
        _logger.info('%r: Open Upload File Dialog', self)
        self._hid.mouse_left_click_on_object(self._get_upload_file_button())
        return UploadDialog(self._api, self._hid).wait_until_appears()

    def open_upload_folder_dialog(self) -> UploadDialog:
        _logger.info('%r: Open Upload Folder Dialog', self)
        upload_folder_button = self._get_tab_overlay().find_child({
            "name": "uploadFolderButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(upload_folder_button)
        return UploadDialog(self._api, self._hid).wait_until_appears()

    def cancel_uploading(self, close_notification=True):
        _logger.info('%r: Cancel uploading', self)
        cancel_uploading_button = self._get_tab_overlay().find_child({
            "name": "cancelButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(cancel_uploading_button)
        if close_notification:
            MessageBox(self._api, self._hid).close()


class _RecordingTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._api = api
        self._hid = hid

    def _get_camera_schedule(self):
        return self._dialog.find_child({
            "name": "CameraScheduleWidget",
            "type": "nx::vms::client::desktop::CameraScheduleWidget",
            "visible": 1,
            })

    def get_enable_recording_checkbox(self):
        checkbox = self._get_camera_schedule().find_child({
            "name": "enableRecordingCheckBox",
            "type": "nx::vms::client::desktop::CheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def is_enabled(self) -> bool:
        return self.get_enable_recording_checkbox().is_checked()

    def ensure_cannot_be_enabled(self):
        _logger.info('%r: Ensure recording cannot be enabled', self)
        assert not self.is_enabled()
        try:
            self.set_enabled(True)
        except RuntimeError as e:
            if "Checkbox state value not changed" in str(e):
                pass
        assert not self.is_enabled()

    def set_enabled(self, value):
        _logger.info('%r: Set recording checkbox value to %s', self, value)
        self.get_enable_recording_checkbox().set(value)

    def toggle_recording_checkbox(self):
        self.get_enable_recording_checkbox().click()

    def set_max_keep_archive(self, days: int = None):
        _logger.info('%r: Set Keep archive for %s day(s) for "Max" parameter', self, days)
        keep_archive_box = self._dialog.find_child({
            "name": "groupBox",
            "type": "QGroupBox",
            "visible": 1,
            })
        max_keep_archive_auto_check_box = keep_archive_box.find_child({
            "name": "checkBoxMaxArchive",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, max_keep_archive_auto_check_box).set(False)
        if days is not None:
            max_keep_archive_field = keep_archive_box.find_child({
                "name": "qt_spinbox_lineedit",
                "occurrence": 2,
                "type": "QLineEdit",
                "visible": 1,
                })
            QLineEdit(self._hid, max_keep_archive_field).type_text(str(days))

    def set_record_always_schedule(self):
        _logger.info('%r: Set recording type to Record Always', self)
        button = self._get_recording_type_button_by_name('recordAlways')
        self._hid.mouse_left_click_on_object(button)

    def set_dont_record_schedule(self):
        _logger.info('%r: Set recording type to Do Not Record', self)
        button = self._get_recording_type_button_by_name('noRecord')
        self._hid.mouse_left_click_on_object(button)

    def set_schedule(self, schedule):
        _logger.info('%r: Set schedule to %s', self, schedule)
        self.select_schedule(schedule)

    def _get_recording_type_button_by_name(self, name):
        button = self._dialog.find_child({
            "name": f"{name}Button",
            "type": "nx::vms::client::desktop::ScheduleBrushSelectableButton",
            "visible": 1,
            })
        return Button(button)

    def _get_schedule_grid(self):
        grid = self._get_camera_schedule().find_child({
            "name": "gridWidget",
            "type": "nx::vms::client::desktop::ScheduleGridWidget",
            "visible": 1,
            })
        return _ScheduleGrid(grid, api=self._api, hid=self._hid)

    def select_schedule(self, schedule):
        _logger.info('%r: Select schedule %s', self, schedule)
        if schedule == 'always':
            self._get_schedule_grid().select_all()
        else:
            raise RuntimeError(f'Unknown schedule: {schedule}')

    def has_license_message(self, message):
        license_message = self._get_camera_schedule().find_child({
            "name": "licenseUsageLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return message in QLabel(license_message).get_text()


class _ScheduleGrid:

    def __init__(self, schedule_area_obj: Widget, api: TestKit, hid: HID):
        self._obj = schedule_area_obj
        self._api = api
        self._hid = hid

    def select_all(self):
        # Click ScheduleGrid at "select all" position.
        _logger.info('%r: Click Select All')
        self._hid.mouse_left_click(self._obj.bounds().top_left().right(25).down(15))


class _DewarpingTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._hid = hid

    def _get_enable_dewarping_checkbox(self):
        checkbox = self._dialog.find_child({
            "checkable": True,
            "id": "enableSwitch",
            "text": "Dewarping",
            "type": "SwitchButton",
            "unnamed": 1,
            "visible": True,
            })
        return Checkbox(self._hid, checkbox)

    def get_dewarping_checkbox_state(self):
        return self._get_enable_dewarping_checkbox().is_checked()

    def enable_dewarping(self):
        _logger.info('%r: Enable dewarping', self)
        self._get_enable_dewarping_checkbox().set(True)

    def disable_dewarping(self):
        _logger.info('%r: Disable dewarping', self)
        self._get_enable_dewarping_checkbox().set(False)

    def set_equirectangular_dewarping_mode(self):
        _logger.info('%r: Set 360° Equirectangular dewarping mode', self)
        dewarping_mode_combo = self._dialog.find_child({
            "id": "typeComboBox",
            "type": "ComboBox",
            "unnamed": 1,
            "visible": True,
            })
        QMLComboBoxIncremental(dewarping_mode_combo).select('360° Equirectangular')

    def are_horizontal_options_accessible(self) -> bool:
        container = self._dialog.find_child(self._tab_widget_locator)
        overlay = container.find_child({
            "type": "QQuickWidget",
            "unnamed": 1,
            "visible": True,
            })
        horizontal_alpha_text = overlay.find_child({
            "echoMode": 0,
            "id": "textInput",
            "occurrence": 1,
            "type": "TextInput",
            "unnamed": 1,
            "visible": True,
            "enabled": True,
            })
        if not horizontal_alpha_text.is_accessible_timeout(0.5):
            _logger.info('%r: Horizontal alfa text is not accessible', self)
            return False
        horizontal_beta_text = overlay.find_child({
            "echoMode": 0,
            "id": "textInput",
            "occurrence": 2,
            "type": "TextInput",
            "unnamed": 1,
            "visible": True,
            "enabled": True,
            })
        if not horizontal_beta_text.is_accessible_timeout(0.5):
            _logger.info('%r: Horizontal beta text is not accessible', self)
            return False
        return True

    def get_dewarping_preview_equirectangular(self) -> ImageCapture:
        resource_preview = self._dialog.find_child({
            "id": "preview",
            "type": "ResourcePreview",
            "unnamed": 1,
            "visible": True,
            })
        dewarping_preview_equirectangular = resource_preview.find_child({
            "id": "overlayHolder",
            "type": "Item",
            "unnamed": 1,
            "visible": True,
            })
        return dewarping_preview_equirectangular.image_capture()


class _ExpertTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._hid = hid

    def _get_tab_overlay_locator(self):
        return self._dialog.find_child({
            "name": "CameraExpertSettingsWidget",
            "type": "nx::vms::client::desktop::CameraExpertSettingsWidget",
            "visible": 1,
            })

    def set_logical_id(self, value):
        _logger.info('%r: Set logical id to %s', self, value)
        logical_id_spinbox = self._get_tab_overlay_locator().find_child({
            "name": "logicalIdSpinBox",
            "type": "QSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, logical_id_spinbox).type_text(str(value))

    def get_logical_id_warning_text(self):
        logical_id_warning_label = self._get_tab_overlay_locator().find_child({
            "name": "logicalIdWarningLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(logical_id_warning_label).get_text()

    def set_do_not_archive_primary_stream(self):
        _logger.info('%r: Set do not archive primary stream checkbox to checked', self)
        do_not_archive_primary_stream = Checkbox(self._hid, self._get_tab_overlay_locator().find_child({
            "name": "checkBoxPrimaryRecorder",
            "type": "QCheckBox",
            "visible": 1,
            }))
        if not do_not_archive_primary_stream.is_checked():
            do_not_archive_primary_stream.set(True)


class _MotionTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._hid = hid

    def _get_tab_overlay(self):
        return self._dialog.find_child({
            "name": "CameraMotionSettingsWidget",
            "type": "nx::vms::client::desktop::CameraMotionSettingsWidget",
            "visible": 1,
            })

    def enable_motion_detection(self):
        _logger.info('%r: Enable motion detection', self)
        motion_detection_checkbox = Checkbox(self._hid, self._get_tab_overlay().find_child({
            "name": "motionDetectionCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            }))
        if not motion_detection_checkbox.is_checked():
            motion_detection_checkbox.set(True)


class _PluginsTab(_BaseTab):

    def __init__(self, dialog_locator, api: TestKit, hid: HID):
        super().__init__(dialog_locator, api)
        self._api = api
        self._hid = hid

    def open_device_agent_settings(self, name: str):
        _logger.info("%r: Open settings for Device Agent '%s'", self, name)
        tab = Widget(self._api, {
            'type': 'EngineMenuItem',
            'text': name,
            })
        self._hid.mouse_left_click_on_object(tab)

    def enable_plugin(self, name):
        self.open_device_agent_settings(name)
        self._get_enable_plugin_checkbox().set(True)

    def plugin_is_enabled(self, name):
        self.open_device_agent_settings(name)
        return self._get_enable_plugin_checkbox().is_checked()

    def _get_enable_plugin_checkbox(self):
        checkbox = self._dialog.find_child({
            "id": "enableSwitch",
            "type": "SwitchIcon",
            "unnamed": 1,
            "visible": True,
            })
        return SwitchIcon(checkbox, self._hid)

    def get_checkboxes(self):
        checkboxes = self._dialog.find_children({
            "type": "CheckBox",
            "visible": 1,
            "id": "checkBox",
            })
        return [Checkbox(self._hid, checkbox) for checkbox in checkboxes]
