# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Optional

from gui.desktop_ui.dialogs.upload import CustomUploadDialog
from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.media_capturing import ImagePiecePercentage
from gui.desktop_ui.media_capturing import Screenshot
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.messages import ProgressDialog
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.widget import WidgetIsNotAccessible
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMLComboBox
from gui.desktop_ui.wrappers import QPlainTextEdit
from gui.desktop_ui.wrappers import QSlider
from gui.desktop_ui.wrappers import QSpinBox
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _Feature:

    def __init__(
            self,
            select_button_name: str,
            tab_name: str,
            api: TestKit,
            hid: HID):
        self._export_settings_dialog = BaseWindow(api=api, locator_or_obj={
            "name": "ExportSettingsDialog",
            "type": "nx::vms::client::desktop::ExportSettingsDialog",
            "visible": 1,
            })
        self._select_button_name = select_button_name
        self._tab_name = tab_name
        self._api = api
        self._hid = hid

    def _get_camera_tab(self):
        return Widget(self._api, {
            "name": "cameraTab",
            "type": "QWidget",
            "visible": 1,
            })

    def _get_export_settings(self):
        return self._get_camera_tab().find_child({
            "name": "mediaExportSettingsWidget",
            "type": "QStackedWidget",
            "visible": 1,
            })

    def _get_select_button(self) -> Button:
        select_button = self._get_camera_tab().find_child({
            "name": self._select_button_name,
            "type": "nx::vms::client::desktop::SelectableTextButton",
            "visible": 1,
            })
        return Button(select_button)

    def _get_close_button(self) -> Button:
        close_button = self._get_select_button()._widget.find_child({
            "type": "nx::vms::client::desktop::CloseButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(close_button)

    def enabled(self) -> bool:
        # Feature is included in export but not currently open for editing.
        return self._get_close_button().is_accessible()

    def _get_overlay(self) -> Widget:
        type_name = self._tab_name[0].upper() + self._tab_name[1:]
        locator_6_0 = {
            "name": f"{self._tab_name}SettingsPage",
            "type": f"nx::vms::client::desktop::{type_name}OverlaySettingsWidget",
            }
        locator_6_1 = {
            "name": f"{self._tab_name}SettingsPage",
            "type": f"nx::vms::client::desktop::{type_name}SettingsWidget",
            }
        overlay = self._get_export_settings().find_child(locator_6_0)
        if not overlay.is_accessible_timeout(0):
            return self._get_export_settings().find_child(locator_6_1)
        return overlay

    def _is_active(self) -> bool:
        # Feature is currently open for editing.
        return self._get_overlay().is_accessible_timeout(0.5)

    def _wait_for_accessible(self, timeout: float = 3):
        self._get_overlay().wait_for_accessible(timeout)

    def _wait_for_inaccessible(self, timeout: float = 3):
        self._get_overlay().wait_for_inaccessible(timeout)

    def exists(self) -> bool:
        # Feature may be absent, depending on what we export.
        return self._get_select_button().is_accessible_timeout(0.5)

    def disable(self):
        _logger.info('Disable %s feature', self)
        button = self._get_close_button()
        if button.is_accessible_timeout(0.1):
            self._hid.mouse_left_click_on_object(button)
            self._wait_for_inaccessible()
        else:
            _logger.info('Feature %s is already disabled', self)

    def make_active(self):
        _logger.info('Make active %s feature', self)
        if not self._is_active():
            self._hid.mouse_left_click_on_object(self._get_select_button())
            self._wait_for_accessible()
        time.sleep(.5)

    def delete(self):
        _logger.info('Delete %s feature', self)
        delete_button_object = self._export_settings_dialog.find_child({
            "name": "deleteButton",
            "type": "QPushButton",
            "visible": 1,
            })
        delete_button = Button(delete_button_object)
        if self._is_active():
            self._hid.mouse_left_click_on_object(delete_button)
            self._wait_for_inaccessible()
        delete_button.wait_for_inaccessible()


class _BookmarkFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "bookmarkButton",
            "bookmark",
            api,
            hid,
            )

    def set_size(self, font_size):
        _logger.info('%s feature: Set font size to %s', self, font_size)
        spinbox = self._export_settings_dialog.find_child({
            'objectName': 'fontSizeSpinBox',
            'type': 'QSpinBox',
            'visible': True,
            })
        QSpinBox(self._hid, spinbox).type_text(str(font_size))

    def _get_bookmarks_description_checkbox(self):
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "descriptionCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox_object)

    def set_description_checkbox(self, value):
        _logger.info(
            '%r feature: Set description checkbox value to %s',
            self, value)
        self._get_bookmarks_description_checkbox().set(value)

    def description_checkbox_is_set(self):
        return self._get_bookmarks_description_checkbox().is_checked()


class _TimestampFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "timestampButton",
            "timestamp",
            api,
            hid,
            )

    def _get_font_size_spinbox(self):
        spinbox = self._export_settings_dialog.find_child({
            "name": "qt_spinbox_lineedit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QSpinBox(self._hid, spinbox)

    def set_size(self, font_size):
        _logger.info('%s feature: Set font size: %s', self, font_size)
        self._get_font_size_spinbox().type_text(str(font_size))

    def verify_size(self, font_size):
        _logger.info('%s feature: Verify font size is %s', self, font_size)
        return self._get_font_size_spinbox().get_text() == str(font_size)

    def verify_format(self, _format):
        _logger.info('%s feature: Verify format is %s', self, _format)
        format_box = self._export_settings_dialog.find_child({
            "name": "formatComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, format_box).current_item() == str(_format)


class _ImageFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "imageButton",
            "image",
            api,
            hid,
            )

    def set(
            self,
            file_path: str,
            size: int = 500,
            opacity: int = 100,
            position: str = 'bottom_right',
            ):
        _logger.info(
            '%r feature: Set image with parameters:'
            ' File path %s, size %s, opacity %s, position %s',
            self, file_path, size, opacity, position)
        self.set_image(file_path)
        self.set_size(size)
        self.set_opacity(opacity)
        _ExportPreview(self._api, self._hid).set_image_position(position)

    def set_image(self, file_path: str):
        _logger.info('%s feature: Set image path %s', self, file_path)
        browse_image_object = self._export_settings_dialog.find_child({
            "name": "browseButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(browse_image_object)
        dialog = CustomUploadDialog(self._api, self._hid)
        # Sometimes on CI first click is not performed, click one more time if dialog is not open.
        if not dialog.is_accessible_timeout(3):
            self._hid.mouse_left_click_on_object(browse_image_object)
            dialog.wait_for_accessible()
        dialog.upload_file(file_path, time_sleep=0)

    def set_size(self, value: int):
        _logger.info('%s feature: Set size value: %s', self, value)
        size_slider_object = self._export_settings_dialog.find_child({
            "name": "sizeSlider",
            "type": "QSlider",
            "visible": 1,
            })
        # Value is in range [0;1332].
        QSlider(size_slider_object, min_value=0, max_value=1332).set(value)

    def set_opacity(self, value: int):
        _logger.info('%s feature: Set opacity value to %s', self, value)
        opacity_slider_object = self._export_settings_dialog.find_child({
            "name": "opacitySlider",
            "type": "QSlider",
            "visible": 1,
            })
        # Value is in range [0;100].
        QSlider(opacity_slider_object).set(value)


class _TextFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "textButton",
            "text",
            api,
            hid,
            )

    def _get_text_field(self):
        text_field = self._export_settings_dialog.find_child({
            "name": "plainTextEdit",
            "type": "QPlainTextEdit",
            "visible": 1,
            })
        return QPlainTextEdit(text_field)

    def set_text(self, text):
        _logger.info('%s feature: Set text %s', self, text)
        self._get_text_field().type_text(text)

    def set_area_width(self, width):
        _logger.info('%s feature: Set area width value to %s', self, width)
        width_slider = self._export_settings_dialog.find_child({
            "name": "widthSlider",
            "type": "QSlider",
            "visible": 1,
            })
        QSlider(width_slider, min_value=60, max_value=1332).set(int(width))

    def get_text(self):
        return self._get_text_field().get_text()

    def set_size(self, font_size):
        _logger.info('%s feature: Set font size value to %s', self, font_size)
        font_size_slider = self._export_settings_dialog.find_child({
            "name": "fontSizeSpinBox",
            "type": "QSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, font_size_slider).type_text(str(font_size))


class _InfoFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "infoButton",
            "info",
            api,
            hid,
            )

    def _get_camera_checkbox(self):
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "exportCameraNameCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox_object)

    def _get_date_checkbox(self):
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "exportDateCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox_object)

    def is_camera_set(self):
        return self._get_camera_checkbox().is_checked()

    def is_date_set(self):
        return self._get_date_checkbox().is_checked()

    def _get_font_size(self):
        font_size_label_object = self._export_settings_dialog.find_child({
            "name": "qt_spinbox_lineedit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, font_size_label_object).get_text()

    def set_camera(self, value: bool):
        _logger.info('%s feature: Set camera checkbox value to %s', self, value)
        self._get_camera_checkbox().set(value)

    def set_date(self, value: bool):
        _logger.info('%s feature: Set date checkbox value to %s', self, value)
        self._get_date_checkbox().set(value)

    def set_font_size_by_slider(self, size: int):
        _logger.info('%s feature: Set font size to value %s by slider', self, size)
        slider_object = self._export_settings_dialog.find_child({
            "name": "fontSizeSlider",
            "type": "QSlider",
            "visible": 1,
            })
        QSlider(slider_object, max_value=400).set(size)

    def set_font_size_by_spinbox(self, size: int):
        _logger.info('%s feature: Set font size to value %s by spinbox', self, size)
        spinbox_object = self._export_settings_dialog.find_child({
            "name": "fontSizeSpinBox",
            "type": "QSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, spinbox_object).set(int(self._get_font_size()), size)

    def verify_size(self, size: int):
        _logger.info('%s feature: Verify font size is %s', self, size)
        return self._get_font_size() == str(size)


class _RapidReviewFeature(_Feature):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(
            "speedButton",
            "rapidReview",
            api,
            hid,
            )


class _TabFeature(_Feature):
    _upper_exporter_tab = None

    def __init__(
            self,
            select_button_name: str,
            upper_tab_name: str,
            api: TestKit,
            hid: HID,
            ):
        tab_name = "exportMediaSettings"
        self._upper_tab_name = upper_tab_name
        super().__init__(select_button_name, tab_name, api, hid)

    def _get_password_checkbox(self):
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "cryptCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox_object)

    def set_password(self, password: str):
        _logger.info('%s feature: Set password %s', self, password)
        self._get_password_checkbox().set(True)
        password_field_object = self._export_settings_dialog.find_child({
            "name": "passwordEdit_passwordLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        QLineEdit(self._hid, password_field_object).type_text(password)

    def unset_password(self):
        _logger.info('%s feature: Unset password', self)
        self._get_password_checkbox().set(False)

    def is_protection_available(self):
        return self._get_password_checkbox().is_accessible()

    def is_protection_set(self):
        return self._get_password_checkbox().is_checked()

    def _get_upper_exporter_tab(self):
        return Widget(self._api, {
            "name": self._upper_tab_name,
            "type": "QWidget",
            "visible": 1,
            })

    def password_error_text(self):
        group_box = self._get_upper_exporter_tab().find_child({
            "name": "groupBox",
            "type": "QGroupBox",
            "visible": 1,
            })
        password_error_object = group_box.find_child({
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            })
        return QLabel(password_error_object).get_text()

    def _get_tab_widget(self):
        tab_widget = self._export_settings_dialog.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            })
        return TabWidget(tab_widget)

    def _get_overlay(self) -> Widget:
        type_name = self._tab_name[0].upper() + self._tab_name[1:]
        return self._get_export_settings().find_child({
            "name": f"{self._tab_name}Page",
            "type": f"nx::vms::client::desktop::{type_name}Widget",
            })


class SingleExportSettings(_TabFeature):

    def __init__(self, api: TestKit, hid: HID):
        self._tab_name = "cameraTab"
        super().__init__(
            select_button_name="cameraExportSettingsButton",
            upper_tab_name=self._tab_name,
            api=api,
            hid=hid,
            )

    def _get_apply_filters_checkbox(self):
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "filtersCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox_object)

    def get_apply_filters_checkbox_state(self):
        return self._get_apply_filters_checkbox().is_checked()

    def set_apply_filters(self, value: bool):
        _logger.info('%s tab: set apply filters checkbox value to %s', self, value)
        self._get_apply_filters_checkbox().set(value)

    def is_open(self):
        return self._get_tab_widget().get_current_index() == 0

    def make_active(self):
        if not self.is_open():
            _logger.info('%s tab: Make active', self)
            ExportSettingsDialog(self._api, self._hid).select_tab("Single Camera")


class MultiExportSettings(_TabFeature):

    def __init__(self, api: TestKit, hid: HID):
        self._tab_name = "layoutTab"
        super().__init__(
            select_button_name="layoutExportSettingsButton",
            upper_tab_name=self._tab_name,
            api=api,
            hid=hid,
            )

    def make_active(self):
        if not self.is_open():
            _logger.info('%s tab: Make active', self)
            ExportSettingsDialog(self._api, self._hid).select_tab("Multi Video")

    def set_read_only(self, value):
        _logger.info('%s tab: set read only checkbox value to %s', self, value)
        checkbox_object = self._export_settings_dialog.find_child({
            "name": "readOnlyCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, checkbox_object).set(value)

    def is_open(self):
        return self._get_tab_widget().get_current_index() == 1


class _ExportPreview:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def _get_media_frame(self) -> Widget:
        return Widget(self._api, {
            "name": "mediaFrame",
            "type": "QFrame",
            "visible": 1,
            })

    def _get_overlay_by_name(self, name: str) -> Widget:
        return self._get_media_frame().find_child({
            "name": name,
            "type": "nx::vms::client::desktop::ExportOverlayWidget",
            "visible": 1,
            })

    def _get_preview_bounds(self):
        preview = self._get_media_frame().find_child({
            "name": "mediaPreviewWidget",
            "type": "nx::vms::client::desktop::AsyncImageWidget",
            "visible": 1,
            })
        return preview.bounds()

    def ratio(self):
        return self._get_preview_bounds().ratio()

    def _get_drag_coords(self, position: str) -> ScreenPoint:
        if position == 'top_left':
            return self._get_preview_bounds().top_left()
        elif position == 'top_center':
            return self._get_preview_bounds().top_center()
        elif position == 'top_right':
            return self._get_preview_bounds().top_right()
        elif position == 'bottom_left':
            return self._get_preview_bounds().bottom_left()
        elif position == 'bottom_right':
            return self._get_preview_bounds().bottom_right()
        elif position == 'center':
            return self._get_preview_bounds().center()
        raise RuntimeError('Unknown position')

    def _set_overlay_position(self, position: str, overlay: Widget):
        target = self._get_drag_coords(position)
        self._hid.mouse_drag_and_drop(overlay.center(), target)
        time.sleep(1)

    @classmethod
    def _verify_overlay_bounds_in_preview_bounds(cls, overlay_bounds, preview_bounds):
        if overlay_bounds.x - preview_bounds.x < 0:
            raise RuntimeError(
                "Wrong x-coordinates.\n"
                f"Overlay bounds, x coordinate: {overlay_bounds.x}\n"
                f"Preview bounds, x coordinate: {preview_bounds.x}")
        if overlay_bounds.y - preview_bounds.y < 0:
            raise RuntimeError(
                "Wrong y-coordinates.\n"
                f"Overlay bounds, y coordinate: {overlay_bounds.y}\n"
                f"Preview bounds, x coordinate: {preview_bounds.y}")
        # We allow for overlay width and height to be one px bigger than in the preview.
        # It can happen now, we consider it is ok, but need to distinguish this case
        # from wrong positioning.
        if preview_bounds.width - overlay_bounds.width < -1:
            raise RuntimeError(
                "Wrong width.\n"
                f"Overlay bounds, width: {overlay_bounds.width}\n"
                f"Preview bounds, width: {preview_bounds.width}")
        if preview_bounds.height - overlay_bounds.height < -1:
            raise RuntimeError(
                "Wrong height.\n"
                f"Overlay bounds, height: {overlay_bounds.height}\n"
                f"Preview bounds, height: {preview_bounds.height}")

    def _get_overlay_position(self, overlay: Widget) -> Optional[ImagePiecePercentage]:
        if not overlay.is_accessible():
            return None
        preview_bounds = self._get_preview_bounds()
        self._verify_overlay_bounds_in_preview_bounds(overlay.bounds(), preview_bounds)
        relative_x = overlay.bounds().x - self._get_preview_bounds().x
        relative_y = overlay.bounds().y - self._get_preview_bounds().y
        offset_x = relative_x / self._get_preview_bounds().width
        offset_y = relative_y / self._get_preview_bounds().height
        width = overlay.bounds().width / self._get_preview_bounds().width
        height = overlay.bounds().height / self._get_preview_bounds().height
        return ImagePiecePercentage(
            min(offset_x, 1),
            min(offset_y, 1),
            min(width, 1),
            min(height, 1),
            )

    def set_image_position(self, position: str):
        _logger.info('%r: Set image position to %s', self, position)
        self._set_overlay_position(
            position, self._get_overlay_by_name("image"))

    def set_timestamp_position(self, position: str):
        _logger.info('%r: Set timestamp position to %s', self, position)
        self._set_overlay_position(
            position,
            self._get_overlay_by_name("timestamp"))

    def set_text_position(self, position: str):
        _logger.info('%r: Set text position to %s', self, position)
        self._set_overlay_position(
            position,
            self._get_overlay_by_name("text"))

    def set_bookmark_position(self, position: str):
        _logger.info('%r: Set bookmark position to %s', self, position)
        self._set_overlay_position(
            position,
            self._get_overlay_by_name("bookmark"),
            )

    def set_info_position(self, position: str):
        _logger.info('%r: Set info position to %s', self, position)
        self._set_overlay_position(
            position,
            self._get_overlay_by_name("info"),
            )

    def get_text_position(self):
        return self._get_overlay_position(self._get_overlay_by_name("text"))

    def get_image_position(self):
        return self._get_overlay_position(self._get_overlay_by_name("image"))

    def get_timestamp_position(self):
        return self._get_overlay_position(self._get_overlay_by_name("timestamp"))

    def get_bookmark_position(self):
        return self._get_overlay_position(self._get_overlay_by_name("bookmark"))

    def validate_overlay_positions(self):
        # if positions are not valid, we'll get an error here
        _logger.info('%r: Validate overlay positions', self)
        self.get_text_position()
        self.get_image_position()
        self.get_timestamp_position()
        self.get_bookmark_position()


class _SingleCameraExporter:
    export_formats = dict(
        mkv='Matroska (*.mkv)',
        avi='Audio Video Interleave (*.avi)',
        mp4='MPEG-4 Part 14 (*.mp4)',
        nov='Network Optix Media File (*.nov)',
        exe='Executable Network Optix Media File (*.exe)',
        )

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._export_settings_dialog = BaseWindow(api=api, locator_or_obj={
            "name": "ExportSettingsDialog",
            "type": "nx::vms::client::desktop::ExportSettingsDialog",
            "visible": 1,
            })

    def _get_browse_button(self):
        return Button(self._export_settings_dialog.find_child({
            "name": "browsePushButton",
            "type": "QPushButton",
            "visible": 1,
            }))

    def _get_field_with_name(self, left_text: str) -> QLineEdit:
        folder_label_locator = {
            "text": left_text.capitalize(),
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            }
        field_locator = {
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            "leftWidget": folder_label_locator,
            }
        name_field = self._export_settings_dialog.find_child(field_locator)
        return QLineEdit(self._hid, name_field)

    def _get_extensions_combobox(self):
        combobox_object = self._export_settings_dialog.find_child({
            "name": "extensionsComboBox",
            "type": "nx::vms::client::desktop::AdvancedComboBox",
            "visible": 1,
            })
        return QMLComboBox(combobox_object)

    def current_path(self):
        folder = self._get_field_with_name('Folder').get_text()
        filename = self._get_field_with_name('Name').get_text()
        current_combobox_text = self._get_extensions_combobox().current_item()
        reversed_extensions = {value: key for key, value in self.export_formats.items()}
        extension = reversed_extensions[current_combobox_text]
        return folder, f'{filename}.{extension}'

    def set_folder(self, value: str):
        _logger.info('%r: Set folder %s', self, value)
        self._hid.mouse_left_click_on_object(self._get_browse_button())
        dialog = UploadDialog(self._api, self._hid).wait_until_appears()
        dialog.upload_folder(value, 0)

    def set_name(self, value):
        _logger.info('%r: Set name %s', self, value)
        self._get_field_with_name('Name').type_text(value)

    def set_extension(self, extension: str):
        _logger.info('%r: Set extension %s', self, extension)
        self._get_extensions_combobox().select(self.export_formats[extension])

    def click_export_button(self):
        _logger.info('%r: Start export', self)
        button_object = self._export_settings_dialog.find_child({
            "text": "Export",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button_object)

    def export(self):
        _logger.info('%r: Start export', self)
        self.click_export_button()
        self._wait_until_progress_dialog_appeared()
        message_dialog = MessageBox(self._api, self._hid)
        self._wait_until_export_completed_appeared(message_dialog)
        message_dialog.close_by_button('OK')

    def capture_preview(self) -> Screenshot:
        preview_frame = self._export_settings_dialog.find_child({
            "type": "nx::vms::client::desktop::AsyncImageWidget",
            "visible": 1,
            })
        return preview_frame.image_capture()

    def _wait_until_progress_dialog_appeared(self):
        _logger.debug("%r: Wait until progress dialog appears", self)
        started_at = time.monotonic()
        while True:
            try:
                ProgressDialog(self._api).wait_until_open(timeout=60)
            except WidgetIsNotAccessible:
                _logger.debug('The ProgressDialog appeared briefly and was not detected')
                break
            else:
                break
        _logger.debug(
            "%r: Progress dialog appeared. It took %.2f seconds",
            self, time.monotonic() - started_at)

    def _wait_until_export_completed_appeared(self, message_dialog: MessageBox):
        _logger.debug("%r: Wait until message box 'Export completed' appears", self)
        delay = 1
        started_at = time.monotonic()
        message_dialog.wait_until_appears(timeout=300)
        _logger.info("Export status Message box appeared")
        while True:
            labels = message_dialog.get_labels()
            if 'Export completed' in labels:
                break
            if 'Export failed' in labels:
                raise RuntimeError('Export failed')

            elapsed_time = time.monotonic() - started_at
            message = f"Message box doesn't have label 'Export completed' after {elapsed_time}"
            if elapsed_time > 300:
                raise RuntimeError(f"Timed out: {message}")
            _logger.debug("%s: Retry in %d sec", message, delay)
            time.sleep(delay)
        _logger.debug(
            "%r: The message box appeared. It took %.2f seconds",
            self, time.monotonic() - started_at)


class _MultiVideoExporter(_SingleCameraExporter):
    export_formats = dict(
        nov='Network Optix Media File (*.nov)',
        exe='Executable Network Optix Media File (*.exe)',
        )


class ExportSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "ExportSettingsDialog",
            "type": "nx::vms::client::desktop::ExportSettingsDialog",
            "visible": 1,
            })
        self.preview = _ExportPreview(api, hid)
        self.multi_export_settings = MultiExportSettings(self._api, hid)
        self.single_camera_settings = SingleExportSettings(self._api, hid)
        self.text_feature = _TextFeature(self._api, hid)
        self.info_feature = _InfoFeature(self._api, hid)
        self.image_feature = _ImageFeature(self._api, hid)
        self.bookmark_feature = _BookmarkFeature(self._api, hid)
        self.timestamp_feature = _TimestampFeature(self._api, hid)
        self.rapid_review_feature = _RapidReviewFeature(self._api, hid)

    def _get_tab(self):
        tab_object = self._dialog.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            })
        return TabWidget(tab_object)

    def make_bookmark_feature_active(self):
        self.bookmark_feature.make_active()
        return self.bookmark_feature

    def make_timestamp_feature_active(self):
        self.timestamp_feature.make_active()
        return self.timestamp_feature

    def make_image_feature_active(self):
        self.image_feature.make_active()
        return self.image_feature

    def make_text_feature_active(self):
        self.text_feature.make_active()
        return self.text_feature

    def make_info_feature_active(self):
        self.info_feature.make_active()
        return self.info_feature

    def is_open(self):
        return self._dialog.is_open()

    def select_tab(self, name):
        _logger.info('%r: Select tab %s', self, name)
        tab = self._get_tab().find_tab(name)
        self._hid.mouse_left_click_on_object(tab)
        time.sleep(2)

    def has_tab(self, name):
        self._get_tab().has_tab(name)

    def disable_all_features(self):
        _logger.info('%r: Disable all features', self)
        for feature in [
                self.bookmark_feature,
                self.timestamp_feature,
                self.image_feature,
                self.text_feature,
                self.rapid_review_feature,
                ]:
            if feature.exists():
                feature.disable()
        self.single_camera_settings.make_active()
        self.single_camera_settings.set_apply_filters(False)

    def disable_all_multi_video_features(self):
        _logger.info('%r: Disable all multi video features', self)
        self.multi_export_settings.set_read_only(False)
        self.multi_export_settings.unset_password()

    def capture_preview(self) -> Screenshot:
        return self.exporter().capture_preview()

    def exporter(self):
        # Returns current exporter class which depends on current active tab.
        # They're almost identical but are based on different sq objects.
        if self._get_tab().get_current_index() == 0:
            return _SingleCameraExporter(self._api, self._hid)
        return _MultiVideoExporter(self._api, self._hid)

    def settings(self):
        # Returns object of current settings class, which depends on current active tab.
        # They're almost identical but are based on different sq objects.
        if self._get_tab().get_current_index() == 0:
            return SingleExportSettings(self._api, self._hid)
        return MultiExportSettings(self._api, self._hid)

    def export(self):
        self.exporter().export()

    def export_with_specific_path(self, path):
        exporter = self.exporter()
        exporter.set_folder(str(path.parent))
        exporter.set_name(path.stem)
        exporter.set_extension(path.suffix.strip('.'))
        exporter.export()
