# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from typing import Collection
from typing import List
from typing import Union

from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.dialogs.check_file_watermark import CheckFileWatermarkDialog
from gui.desktop_ui.dialogs.image_enhancement import ImageEnhancementDialog
from gui.desktop_ui.dialogs.save_screenshot import SaveScreenshotDialog
from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.file_settings import FileSettings
from gui.desktop_ui.layouts import LayoutNameDialog
from gui.desktop_ui.layouts import LayoutSettings
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.main_window import get_graphics_view_object
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.media_capturing import ImagePiecePercentage
from gui.desktop_ui.media_capturing import Screenshot
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import HtmlTextItem
from gui.desktop_ui.wrappers import QCheckableButton
from gui.desktop_ui.wrappers import QMenu
from gui.testkit.hid import ClickableObject
from gui.testkit.hid import ControlModifier
from gui.testkit.hid import HID
from gui.testkit.testkit import TestKit

_logger = logging.getLogger(__name__)


def get_screen_object(api: TestKit) -> Widget:
    return get_graphics_view_object(api).find_child({
        "acceptDrops": "no",
        "enabled": "yes",
        "focusable": "yes",
        "movable": "yes",
        "selectable": "yes",
        "type": "QnMediaResourceWidget",
        "visible": "yes",
        })


def check_toolbar_ok(api: TestKit):
    # Check that toolbar is in the upper-left corner and horizontal.
    widget_bounds = get_screen_object(api).bounds()
    main_window_locator = {
        "type": "nx::vms::client::desktop::MainWindow",
        "unnamed": 1,
        "visible": 1,
        }
    graphics_view_locator = {
        "type": "QnGraphicsView",
        "unnamed": 1,
        "visible": 1,
        "window": main_window_locator,
        }
    resource_widget = {
        "acceptDrops": "no",
        "container": graphics_view_locator,
        "enabled": "yes",
        "focusable": "yes",
        "movable": "yes",
        "selectable": "yes",
        "type": "QnMediaResourceWidget",
        "visible": "yes",
        }
    overlay_locator = {
        "acceptDrops": "no",
        "container": resource_widget,
        "enabled": "yes",
        "focusable": "no",
        "movable": "no",
        "selectable": "no",
        "type": "QnHudOverlayWidget",
        "visible": "yes",
        }
    viewport_locator = {
        "acceptDrops": "no",
        "container": overlay_locator,
        "enabled": "yes",
        "focusable": "no",
        "movable": "no",
        "selectable": "no",
        "type": "QnViewportBoundWidget",
        "visible": "yes",
        }
    bar = Widget(api, {
        "acceptDrops": "no",
        "container": viewport_locator,
        "enabled": "yes",
        "focusable": "no",
        "movable": "no",
        "selectable": "no",
        "type": "QnResourceTitleItem",
        "visible": "yes",
        })
    bar_bounds = bar.bounds()
    toolbar_ok = (
            abs(bar_bounds.x - widget_bounds.x) < 7
            and abs(bar_bounds.y - widget_bounds.y) < 7
            and bar_bounds.width > 100
            and bar_bounds.height < 50)
    return toolbar_ok


class SceneItem(ClickableObject):
    # Abstract sq name of the scene item, becomes specific if you set objectName inside it.
    _main_window_locator = {
        "type": "nx::vms::client::desktop::MainWindow",
        "unnamed": 1,
        "visible": 1,
        }
    _graphics_view_locator = {
        "type": "QnGraphicsView",
        "unnamed": 1,
        "visible": 1,
        "window": _main_window_locator,
        }
    _abstract_squish_name = {
        "acceptDrops": "no",
        "container": _graphics_view_locator,
        "enabled": "yes",
        "focusable": "yes",
        "movable": "yes",
        "selectable": "yes",
        "type": "QnMediaResourceWidget",
        "visible": "yes",
        }

    def __init__(self, api: TestKit, hid: HID, name, occurrence: int = 1):
        # This is an attribute of scene item, that allows to identify it among others.
        self.name = name
        self.occurrence = occurrence
        self.squish_name = {
            **self._abstract_squish_name,
            'objectName': self.name,
            'occurrence': str(occurrence),
            }
        self._obj = Widget(api, self.squish_name)
        self._api = api
        self._hid = hid

    def __repr__(self):
        return f'{self.__class__.__name__}({self.name})'

    def _get_button_by_tooltip_text(self, text):
        return self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "selectable": "no",
            "toolTip": text,
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })

    def _get_ptz_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("PTZ <b>(P)</b>"))

    def _get_dewarping_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("Dewarping <b>(D)</b>"))

    def _get_motion_search_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("Motion Search <b>(Alt+M)</b>"))

    def _get_information_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("Information <b>(I)</b>"))

    def _get_screenshot_button(self):
        return Button(self._get_button_by_tooltip_text("Screenshot <b>(Alt+S)</b>"))

    def _get_rotate_button(self):
        return Button(self._get_button_by_tooltip_text("Rotate <b>(Alt+drag)</b>"))

    def _get_close_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("Close <b>(Del)</b>"))

    def _get_create_zoom_window_button(self):
        return QCheckableButton(self._hid, self._get_button_by_tooltip_text("Create Zoom Window <b>(W)</b>"))

    def get_button_by_key(self, name) -> Union[Button, QCheckableButton]:
        buttons = {
            'PTZ': self._get_ptz_button,
            'Dewarping': self._get_dewarping_button,
            'Motion Search': self._get_motion_search_button,
            'Information': self._get_information_button,
            'Screenshot': self._get_screenshot_button,
            'Rotate': self._get_rotate_button,
            'Close': self._get_close_button,
            'Create Zoom Window': self._get_create_zoom_window_button,
            }
        return buttons[name]()

    def wait_for_inaccessible(self):
        self._obj.wait_for_inaccessible()

    def wait_for_accessible(self, timeout: float = 3):
        self._obj.wait_for_accessible(timeout)

    def is_selected(self):
        return self._obj.wait_property('selected')

    def get_available_buttons(self) -> list:
        button_keys = [
            'PTZ',
            'Dewarping',
            'Motion Search',
            'Information',
            'Screenshot',
            'Rotate',
            'Close',
            'Create Zoom Window',
            ]
        return [
            self.get_button_by_key(button_key) for button_key in button_keys
            if self.has_button(button_key)]

    def is_expanded(self) -> bool:
        main_window_bounds = MainWindow(self._api, self._hid).bounds()
        width, height = main_window_bounds.width, main_window_bounds.height
        # Actual width and height in fullscreen mode is off by several pixels.
        bounds = self.bounds()
        return abs(width - bounds.width) < 10 and abs(height - bounds.height) < 10

    def wait_for_expanded(self):
        start_time = time.monotonic()
        while True:
            if self.is_expanded():
                return
            if time.monotonic() - start_time > 2:
                raise RuntimeError("The scene item is not expanded after timeout")
            time.sleep(.1)

    def wait_for_window_mode(self):
        start_time = time.monotonic()
        while True:
            if not self.is_expanded():
                return
            if time.monotonic() - start_time > 2:
                raise RuntimeError("Client is not in window mode after timeout")
            time.sleep(.1)

    def resize_at_right(self, delta_x):
        _logger.info('%r: Resize at right', self)
        start_coord = self._obj.bounds().middle_right()
        target_coord = start_coord.right(delta_x)
        self._hid.mouse_press(start_coord)
        time.sleep(2)
        self._hid.mouse_move(target_coord)
        time.sleep(2)
        self._hid.mouse_release(target_coord)
        time.sleep(2)

    def resize_at_top(self, delta_y):
        _logger.info('%r: Resize at top', self)
        start_coord = self._obj.bounds().top_center()
        target_coord = start_coord.up(delta_y)
        self._hid.mouse_press(start_coord)
        time.sleep(2)
        self._hid.mouse_move(target_coord)
        time.sleep(2)
        self._hid.mouse_release(target_coord)
        time.sleep(2)

    def drop_on(self):
        # TODO: Should check.
        self._hid.mouse_move(self.bounds().top_left().right(30).down(30))
        self._hid.mouse_release(self.center())

    def duplicate(self):
        _logger.info('%r: Duplicate', self)
        self._hid.keyboard_press('Ctrl')
        self._hid.mouse_native_drag_and_drop(self.center(), self.center().down(100))
        self._hid.keyboard_release('Ctrl')
        time.sleep(1)

    def hover(self):
        _logger.info('%r: Hover', self)
        Scene(self._api, self._hid).ensure_not_obscured()
        self._hid.mouse_move(self.center())
        time.sleep(1)

    def _is_accessible_timeout(self, timeout: float):
        # Timeout in seconds.
        return self._obj.is_accessible_timeout(timeout)

    def measure_show_time(self):
        started_at = time.monotonic()
        while True:
            if not self._is_accessible_timeout(1):
                break
            time.sleep(1)
        return time.monotonic() - started_at

    def is_reddish(self):
        """Tell if disallowed to resize another item on this.

        When one of the scene items is resized,
        determine the cell in which current item is located.
        Grid that appears when scene items are moved, resized etc.
        Cell of a grid that appears when scene items are moved, resized etc.
        Can be red or green, depending on whether it blocks operation or not.
        """
        grid = get_graphics_view_object(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "selectable": "no",
            "type": "QnGridItem",
            "visible": "yes",
            })
        cells = grid.find_children({
            "type": "QnGridHighlightItem",
            "visible": "yes",
            })
        bounds = self.bounds()
        for cell in cells:
            if cell.bounds().contains_rectangle(bounds):
                return cell.wait_for_object().get_attr('color').get_attr('red') == 255
        raise RuntimeError("Cannot find the cell with this item")

    def get_information(self) -> str:
        # Information about the scene item is activated with (i) button.
        self.hover()
        self.click_button('Information')
        information = self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "selectable": "no",
            "type": "QnHtmlTextItem",
            "visible": "yes",
            "occurrence": 1,
            })
        return HtmlTextItem(information).html()

    def click(self):
        _logger.info('%r: Click', self)
        Scene(self._api, self._hid).ensure_not_obscured()
        self._hid.mouse_left_click_on_object(self)

    def double_click(self):
        _logger.info('%r: Double click', self)
        Scene(self._api, self._hid).ensure_not_obscured()
        self._hid.mouse_double_click_on_object(self)

    def right_click(self):
        _logger.info('%r: Right click', self)
        Scene(self._api, self._hid).ensure_not_obscured()
        self._hid.mouse_right_click_on_object(self)

    def ctrl_click(self):
        _logger.info('%r: Ctrl click', self)
        self._hid.mouse_left_click_on_object(self, modifier=ControlModifier)

    def press_key(self, key):
        _logger.info('%r: Press key: <%s>', self, key)
        self.click()
        self._hid.keyboard_hotkeys(key)

    def bounds(self) -> ScreenRectangle:
        return self._obj.bounds()

    def center(self) -> ScreenPoint:
        return self._obj.center()

    def has_button(self, button_key):
        self.hover()
        return self.get_button_by_key(button_key).is_accessible_timeout(0.5)

    def click_button(self, button_key):
        _logger.info('%r: Click button: %s', self, button_key)
        self.hover()
        self._hid.mouse_left_click_on_object(self.get_button_by_key(button_key))

    def activate_button(self, button_key):
        _logger.info('%r: Activate button: %s', self, button_key)
        if not self.button_checked(button_key):
            self.click_button(button_key)
        if not self.button_checked(button_key):
            raise RuntimeError(f'Button {button_key} was not activated')

    def deactivate_button(self, button_key):
        _logger.info('%r: Deactivate button: %s', self, button_key)
        if self.button_checked(button_key):
            self.click_button(button_key)
        if self.button_checked(button_key):
            raise RuntimeError(f'Button {button_key} was not deactivated')

    def button_checked(self, button_key):
        self.hover()
        return self.get_button_by_key(button_key).is_checked()

    def create_zoom_window(self):
        _logger.info('%r: Create zoom window', self)
        objects_count = len(Scene(self._api, self._hid).items())
        self.hover()
        time.sleep(1)
        self._hid.mouse_left_click_on_object(self._get_create_zoom_window_button())
        # Top left corner of scene item - border. Start dragging with a little indent.
        self._hid.mouse_drag_and_drop(
            self.bounds().top_left().down(1).right(1),
            self.center(),
            )
        Scene(self._api, self._hid).wait_for_items_number(objects_count + 1, 10)
        # Need this time.sleep() because client shows wrong picture at the first moment.
        time.sleep(1)

    def rotate(self, degrees: int = 0):
        _logger.info('%r: Rotate', self)
        button = self._get_rotate_button()
        start_point = button.bounds().top_left().down(5).right(5)
        finish = start_point.transform(around=self.center(), rotate=degrees, scale=0.5)
        self.hover()
        try:
            self._hid.mouse_press(button.center())
            time.sleep(1)
            self._hid.mouse_move(finish)
            time.sleep(1)
        finally:
            self._hid.mouse_release(finish)

    def move(self, delta_x=0, delta_y=0):
        _logger.info('%r: Move to delta_x %s, delta_y %s', self, delta_x, delta_y)
        delta_x, delta_y = int(delta_x), int(delta_y)
        self._hid.mouse_drag_and_drop(
            self.center(),
            self.center().right(delta_x).down(delta_y),
            )

    def open_context_menu(self) -> 'SceneItemContextMenu':
        _logger.info('%r: Open context menu', self)
        self.right_click()
        context_menu = SceneItemContextMenu(self._api, self._hid)
        context_menu.wait_for_accessible()
        return context_menu

    def open_save_screenshot_dialog(self) -> SaveScreenshotDialog:
        _logger.info('%r: Open Save Screenshot Dialog', self)
        self.click_button('Screenshot')
        dialog = SaveScreenshotDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog

    def close(self):
        self.click_button('Close')

    def change_size_by_double_click(self):
        _logger.info('%r: Change size by double click', self)
        initial_state = self.is_expanded()
        self._hid.mouse_double_click_on_object(self)
        start_time = time.monotonic()
        while True:
            if self.is_expanded() != initial_state:
                return
            if time.monotonic() - start_time > 3:
                raise RuntimeError(
                    f"Scene item {self.name} did not change size after double click")
            time.sleep(.5)

    def open_in_fullscreen(self):
        _logger.info('%r: Open in full-screen', self)
        self._hid.mouse_double_click_on_object(self)

    def border_of_zoom(self):
        """Return Widget for zoom border.

        Appears after creation of zoom window (Yellow border on parent scene item).
        The object remains available after closing the zoom window, but not visible for user.
        Can be correctly used only for check that border appears, not hide.
        """
        return Widget(self._api, {"container": self.squish_name, "type": "FixedArSelectionItem"})

    def in_tour(self) -> bool:
        return self._obj.wait_property('localActive')

    def set_dewarping(self, mode):
        _logger.info('%r: Set dewarping mode: %s', self, mode)
        mode_counter = 0
        while not str(mode) in self.get_dewarping_value():
            if mode_counter == 4:
                raise RuntimeError("Impossible to set dewarping mode {}".format(mode))
            self._change_dewarping_value()
            mode_counter += 1
            time.sleep(1)

    def _get_dewarping_icon(self):
        button = self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes", "focusable": "yes",
            "movable": "no", "selectable": "no",
            "toolTip": "Change Dewarping Mode",
            "type": "PtzImageButtonWidget", "visible": "yes",
            })
        return QCheckableButton(self._hid, button)

    def get_dewarping_value(self):
        dewarping_value = self._get_dewarping_icon()
        dewarping_value.wait_for_accessible()
        return dewarping_value.get_text()

    def _change_dewarping_value(self):
        current_value = self._get_dewarping_icon().get_text()
        self._hid.mouse_left_click_on_object(self._get_dewarping_icon())
        if self._get_dewarping_icon().get_text() == current_value:
            # This is required as sometimes squish click doesn't pass correct for dewarping icon
            self._hid.mouse_left_click_on_object(self._get_dewarping_icon())
            if self._get_dewarping_icon().get_text() == current_value:
                raise RuntimeError("Dewarping mode is not changed")

    def video_is_playing(self, duration=10):
        # In some cases, the pause widget appears at the bottom of the scene element.
        # We can't stably predict it, so crop the bottom to ignore this behavior.
        percentage = ImagePiecePercentage(0, 0, 1, .9)
        video = self.video_with_fixed_length(duration)
        video.crop_percentage(percentage)
        return video.has_different_frames()

    def video_with_fixed_length(self, length_sec: int):
        _logger.info('%r: Capturing video. Duration: %s second(s)', self, length_sec)
        return self._obj.video(length_sec)

    def image_capture(self):
        _logger.info('%r: Capturing image', self)
        return self._obj.image_capture()

    def has_text_on_position(self, position, texts):
        _logger.info('%r: Looking for text on position: %s', self, position)
        text_comparer = ImageTextRecognition(self.image_capture())
        expected_rectangle = self.image_capture().make_rectangle(position)
        indexes = text_comparer.multiple_line_indexes(texts)
        for index in indexes:
            calculated_rectangle = text_comparer.get_raw_rectangle_by_index(index)
            if not expected_rectangle.contains_rectangle(calculated_rectangle):
                return False
        return True

    def has_timestamp_on_position(self, position):
        _logger.info('%r: Looking for timestamp on position: %s', self, position)
        text_comparer = ImageTextRecognition(self.image_capture())
        expected_rectangle = self.image_capture().make_rectangle(position)
        index = text_comparer.datetime_index()
        calculated_rectangle = text_comparer.get_raw_rectangle_by_index(index)
        if expected_rectangle.contains_rectangle(calculated_rectangle):
            return True
        return False

    def _get_bounding_boxes(self) -> Collection[Widget]:
        analytic_overlay = self._obj.find_child({
            'type': 'nx::vms::client::desktop::AnalyticsOverlayWidget',
            })
        bounding_boxes = analytic_overlay.find_children({
            'type': 'QGraphicsItem',
            'text': '',
            })
        return bounding_boxes

    def get_bounding_boxes_within_timeout(self):
        start_time = time.monotonic()
        while True:
            bounding_boxes = self._get_bounding_boxes()
            if bounding_boxes:
                return bounding_boxes
            # Reduce timeout when VMS-41262 is fixed
            if time.monotonic() - start_time > 20:
                raise RuntimeError("No bounding box found on scene item")
            time.sleep(.1)


class CameraSceneItem(SceneItem):

    def __init__(self, api: TestKit, hid: HID, name):
        super().__init__(api, name=name, hid=hid)
        self._soft_trigger_button_name = {
            "type": "nx::vms::client::desktop::SoftwareTriggerButton",
            "visible": "yes",
            }

    def get_soft_trigger_button(self):
        self.hover()
        return Button(self._obj.find_child(self._soft_trigger_button_name))

    def has_soft_trigger_button(self):
        return bool(self._obj.find_children(self._soft_trigger_button_name))

    def hold_soft_trigger(self, hold_time_sec):
        _logger.info('%r: Hold soft trigger button %s second(s)', self, hold_time_sec)
        button_center = self.get_soft_trigger_button().center()
        self._hid.mouse_press(button_center)
        time.sleep(hold_time_sec)
        self._hid.mouse_release(button_center)

    def has_phrase(self, expected_text) -> bool:
        text_comparer = ImageTextRecognition(self.image_capture())
        return text_comparer.has_line(expected_text)


class ServerSceneItem(SceneItem):
    _main_window_locator = {
        "type": "nx::vms::client::desktop::MainWindow",
        "unnamed": 1,
        "visible": 1,
        }
    _graphics_view_locator = {
        "type": "QnGraphicsView",
        "unnamed": 1,
        "visible": 1,
        "window": _main_window_locator,
        }
    _abstract_squish_name = {
        "acceptDrops": "no",
        "container": _graphics_view_locator,
        "enabled": "yes",
        "focusable": "yes",
        "movable": "yes",
        "selectable": "yes",
        "type": "QnServerResourceWidget",
        "visible": "yes",
        }


class WebPageSceneItem(SceneItem):
    _main_window_locator = {
        "type": "nx::vms::client::desktop::MainWindow",
        "unnamed": 1,
        "visible": 1,
        }
    _graphics_view_locator = {
        "type": "QnGraphicsView",
        "unnamed": 1,
        "visible": 1,
        "window": _main_window_locator,
        }
    _abstract_squish_name = {
        "acceptDrops": "no",
        "container": _graphics_view_locator,
        "enabled": "yes",
        "focusable": "yes",
        "movable": "yes", "selectable": "yes",
        "type": "QnWebResourceWidget",
        "visible": "yes",
        }
    _HEADER_HEIGHT = 50

    def is_open(self):
        return self._obj.is_accessible()

    def hover_to_header(self):
        self._hid.mouse_move(self.bounds().top_center().down(10))

    def close(self):
        _logger.info('%r: Close', self)
        self.hover_to_header()
        self._hid.mouse_left_click_on_object(self.get_button_by_key('Close'))

    def _get_fullscreen_button(self):
        button = self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "objectName": "FullscreenButton",
            "selectable": "no",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        return Button(button)

    def _get_back_button(self):
        button = self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "objectName": "BackButton",
            "selectable": "no",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        return Button(button)

    def _get_refresh_button(self):
        button = self._obj.find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "objectName": "ReloadButton",
            "selectable": "no",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        return Button(button)

    def _get_information_button(self):
        button = self._obj.find_child({
            "enabled": True,
            "objectName": "InformationButton",
            "type": "QnImageButtonWidget",
            "visible": True,
            })
        return Button(button)

    def _get_close_button(self):
        button = self._obj.find_child({
            "enabled": True,
            "objectName": "CloseButton",
            "type": "QnImageButtonWidget",
            "visible": True,
            })
        return Button(button)

    def get_button_by_key(self, name) -> Union[Button, QCheckableButton]:
        buttons = {
            'Close': self._get_close_button,
            'Information': self._get_information_button,
            'Fullscreen': self._get_fullscreen_button,
            'Exit Fullscreen': self._get_fullscreen_button,
            'Back': self._get_back_button,
            'Refresh': self._get_refresh_button,
            }
        return buttons[name]()

    def double_click_by_title(self):
        _logger.info('%r: Double click by title', self)
        Scene(self._api, self._hid).ensure_not_obscured()
        label = self._obj.find_child({"text": self.name})
        self._hid.mouse_double_click_on_object(label)

    def click_button(self, button_key):
        _logger.info('%r: Click button: %s', self, button_key)
        Scene(self._api, self._hid).ensure_not_obscured()
        button = self.get_button_by_key(button_key)
        # Sometimes click goes a bit before the button is hovered so the action is not done.
        self._hid.mouse_move(button.center())
        self._hid.mouse_left_click_on_object(button)
        time.sleep(3)

    def get_information(self) -> str:
        self.click_button("Information")
        # Sometimes information element disappears if mouse is not on the scene item. Perform
        # hover prior to element's check to avoid such situations.
        self.hover()
        information = self._obj.find_child({
            "enabled": True,
            "type": "QnHtmlTextItem",
            "visible": True,
            "occurrence": 1,
            })
        return HtmlTextItem(information).html()

    def click_link(self, text):
        _logger.info('%r: Click link: %s', self, text)
        phrase_center = self.get_phrase_center(text)
        self._hid.mouse_left_click(phrase_center)

    def image(self):
        # This method is needed as currently web engine does not work correctly with image capture.
        # Has to be updated to a normal work with web engine object and not image capture crop.
        obj = self.image_capture()
        return obj.crop(0, obj.get_width(), self._HEADER_HEIGHT, obj.get_height())

    def get_phrase_center(self, phrase):
        _logger.info('%r: Find phrase: %s', self, phrase)
        content = self.image_capture()
        place = ImageTextRecognition(content).get_phrase_rectangle(phrase)
        return place.center()

    def click_on_phrase(self, phrase):
        coordinate = self.get_phrase_center(phrase)
        _logger.info('%r: Click phrase: %s', self, phrase)
        self._hid.mouse_left_click(coordinate)

    def has_phrase(self, expected_text) -> bool:
        text_comparer = ImageTextRecognition(self.image_capture())
        return text_comparer.has_line(expected_text)

    def wait_for_phrase_exists(self, expected_text, timeout: float = 20):
        _logger.info(
            '%r: Wait for text: %s. Timeout: %s second(s)',
            self, expected_text, timeout)
        start_time = time.monotonic()
        while True:
            if self.has_phrase(expected_text):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"No text {expected_text} found")
            time.sleep(.5)

    def wait_for_does_not_have_phrase(self, expected_text, timeout: float = 20):
        _logger.info(
            '%r: Wait for no text: %s. Timeout: %s second(s)',
            self, expected_text, timeout)
        start_time = time.monotonic()
        while True:
            if not self.has_phrase(expected_text):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"Text {expected_text} is seen on the item")
            time.sleep(.5)

    def scroll_to_phrase(
            self,
            phrase_to_hover,
            expected_phrase,
            timeout: float = 20):
        scroll_delta = 2
        scrollable_place = self.get_phrase_center(phrase_to_hover)
        start_time = time.monotonic()
        while True:
            _logger.info(
                '%r: Scrolling to phrase "%s". Timeout %s second(s)',
                self, expected_phrase, timeout)
            scroll_delta *= 8
            self._hid.mouse_scroll(scrollable_place, -scroll_delta)
            time.sleep(.1)
            if self.has_phrase(expected_phrase):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"Text {expected_phrase} not seen on the item")

    def is_expanded(self) -> bool:
        # The WebPageSceneItem may be maximized with a fixed aspect ratio, causing only
        # one dimension to match the main window bounds.
        main_window_bounds = MainWindow(self._api, self._hid).bounds()
        bounds = self.bounds()
        return any([
            abs(main_window_bounds.width - bounds.width) < 10,
            abs(main_window_bounds.height - bounds.height) < 10,
            ])


class IntegrationSceneItem(WebPageSceneItem):
    pass


class Scene:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def first_item_image(self):
        return self.get_first_item().image_capture()

    def get_first_item(self):
        self.ensure_not_obscured()
        items = self.items()
        return items[0]

    def item_image(self, item_index):
        items = self.items_with_occurrence()
        return items[item_index].image_capture()

    def items(self) -> List[SceneItem]:
        # !!! This method returns items in arbitrary order, not the same as visual.
        # For visual order use .items_visually_ordered()
        view = get_graphics_view_object(self._api)
        # TODO: make this function return appropriate object for all classes.
        items = []
        item_widgets = view.find_children({"type": "QnMediaResourceWidget", "visible": "yes"})
        for i, widget in enumerate(item_widgets):
            scene_item = SceneItem(
                api=self._api,
                hid=self._hid,
                name=str(widget.wait_property('objectName')),
                occurrence=i + 1,
                )
            items.append(scene_item)
        webpage_widgets = view.find_children({"type": "QnWebResourceWidget", "visible": "yes"})
        webpage_items = []
        for i, webpage_widget in enumerate(webpage_widgets):
            webpage_item = WebPageSceneItem(
                api=self._api,
                hid=self._hid,
                name=str(webpage_widget.wait_property('objectName')),
                occurrence=i + 1,
                )
            webpage_items.append(webpage_item)
        return items + webpage_items

    def wait_for_items_number(self, expected_number, timeout: float = 3):
        _logger.info(
            '%r: Wait for there are %s Scene items. Timeout: %s second(s)',
            self, expected_number, timeout)
        start_time = time.monotonic()
        while True:
            actual_number = len(self.items())
            if actual_number == expected_number:
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(
                    f"Wrong quantity of items on the scene. "
                    f"Expected {expected_number}, got {actual_number}")
            time.sleep(1)

    def items_visually_ordered(self) -> List[SceneItem]:
        def comparator(i):
            # Top-left-item > top-right-item > bottom-left-item > bottom-right-item.
            return i.bounds().y, i.bounds().x

        return sorted(self.items(), key=comparator)

    def items_with_occurrence(self) -> List[SceneItem]:
        # For items with same name on scene, occurrence number will be added to SceneItem instance.
        names_occurrence = {}
        items = self.items_visually_ordered()
        for item in items:
            if item.name in names_occurrence:
                names_occurrence[item.name] = names_occurrence[item.name] + 1
                item.occurrence = names_occurrence[item.name]
            else:
                names_occurrence[item.name] = 1
                item.occurrence = 1
        return [SceneItem(self._api, self._hid, item.name, item.occurrence) for item in items]

    def _empty_place_coords(self) -> ScreenPoint:
        # Coordinates of some place on scene which MOST LIKELY will be empty even if items
        # exist on the scene. Relative to GraphicsView. We don't have scene as
        # a separate object, so this position is determined as a small shift from top-left-most
        # item or center of overlay if no items present on scene.
        items = self.items_visually_ordered()
        if items:
            return items[0].bounds().top_left().up(5).left(5)
        else:
            return get_graphics_view_object(self._api).center()

    def open_context_menu(self):
        _logger.info('%r: Open context menu', self)
        self._hid.mouse_right_click(self._empty_place_coords())
        QMenu(self._api, self._hid).wait_for_accessible()

    def ensure_not_obscured(self):
        # To prevent anything from obscuring scene items we click at an empty space on scene.
        _logger.info('%r: Click empty place', self)
        self._hid.mouse_left_click(self._empty_place_coords())
        # Wait for the resource tree item tooltip to disappear if existed.
        main_window_locator = {
            "type": "nx::vms::client::desktop::MainWindow",
            "unnamed": 1,
            "visible": 1,
            }
        resource_browser_locator = {
            "name": "ResourceBrowserWidget",
            "type": "QnResourceBrowserWidget",
            "visible": 1,
            "window": main_window_locator,
            }
        resource_tree_tooltip = Widget(self._api, {
            "leftWidget": resource_browser_locator,
            "type": "nx::vms::client::desktop::ThumbnailTooltip",
            "unnamed": 1,
            "visible": 1,
            "window": main_window_locator,
            })
        resource_tree_tooltip.wait_for_inaccessible()
        time.sleep(1)

    def _activate_context_menu_item(self, item_name):
        self.open_context_menu()
        QMenu(self._api, self._hid).activate_items(item_name)

    def select_items_by_ctrl(self, items: List[SceneItem]):
        _logger.info('%r: Select items by ctrl: %r', self, items)
        self.ensure_not_obscured()
        for item in items:
            item.ctrl_click()

    def select_items_dragging(self, quantity: int):
        # This is an attempt to make a universal method to select several items by mouse dragging.
        # However, it doesn't seem possible for all quantities and item setups on scene:
        # for example 3 items in case of   x x   setup of items.
        #                                  x x

        _logger.info('%r: Select items by dragging: Quantity %d', self, quantity)
        self.ensure_not_obscured()
        # Start position is in the upper left corner.
        start = self._empty_place_coords().up(10).right(10)
        item = self.items_visually_ordered()[-quantity]
        end = item.bounds().bottom_left().down(10).right(10)
        self._hid.mouse_drag_and_drop(start, end)

    def start_tour(self):
        _logger.info('%r: Start tour', self)
        self._activate_context_menu_item("Start Tour")

    def stop_tour(self):
        _logger.info('%r: Stop tour', self)
        window_positions_1 = [x.bounds() for x in self.items()]
        self._hid.keyboard_hotkeys('Escape')
        # Check that the scene items have decreased in size at least twice after pressing Esc -
        # this proves that the tour was stopped.
        for _ in range(60):
            time.sleep(.5)
            window_positions_2 = [x.bounds() for x in self.items()]
            if window_positions_1[0].width / 2 > window_positions_2[0].width:
                return
        else:
            raise RuntimeError('Unable to stop tour')

    def save_current_as(self, new_name):
        _logger.info('%r: Save current layout as %r', self, new_name)
        self._activate_context_menu_item("Save Current Layout As...")
        dialog = LayoutNameDialog(self._api, self._hid)
        dialog.get_name_field().type_text(new_name)
        self._hid.mouse_left_click_on_object(dialog.get_save_button())
        time.sleep(2)

    def open_layout_settings(self) -> LayoutSettings:
        _logger.info('%r: Open Layout Settings Dialog', self)
        self._activate_context_menu_item("Layout Settings...")
        return LayoutSettings(self._api, self._hid).wait_until_appears()

    def open_image_as_item(self, image_path):
        self.open_context_menu()
        QMenu(self._api, self._hid).activate_items("Open", "Files...")
        upload_dialog = UploadDialog(self._api, self._hid)
        upload_dialog.wait_for_accessible()
        upload_dialog.upload_file(str(image_path), time_sleep=0)

    def get_background(self) -> Screenshot:
        background = get_graphics_view_object(self._api).find_child({
            "type": "QnGridBackgroundItem",
            'enabled': True,
            "visible": True,
            })
        # o_QnGridBackgroundItem has invalid ScreenRectangle object without set background.
        # When comparing, correlation is not good for some sample backgrounds.
        # If removed from checking, correlation threshold may be increased.
        # The aspect ratio of the background slightly changes
        # due to the specifics of the coverage of the layout cells.
        background_bounds = background.bounds()
        if background_bounds.x < 0 or background_bounds.y < 0:
            raise _BackgroundNotValid(f'Invalid background dimensions: {background_bounds}')
        return background.image_capture()

    def has_background(self):
        try:
            self.get_background()
        except _BackgroundNotValid:
            return False
        return True

    def zoom_up(self):
        _logger.info("%r: Zoom up", self)
        self._hid.mouse_scroll(get_graphics_view_object(self._api).center(), 120)

    def zoom_down(self):
        _logger.info("%r: Zoom down", self)
        self._hid.mouse_scroll(get_graphics_view_object(self._api).center(), -120)

    def wait_until_first_item_is_similar_to(self, expected_image: ImageCapture, timeout: float = 15):
        item = self.get_first_item()
        timeout_at = time.monotonic() + timeout
        while True:
            item_image = item.image_capture()
            if item_image.is_similar_to(expected_image):
                return
            elif time.monotonic() > timeout_at:
                raise RuntimeError(f'Item image is not similar to expected image after {timeout} sec')
            time.sleep(1)


class SceneItemContextMenu(QMenu):
    """Available for Test camera scene, Virtual camera scene and File scene."""

    # Common items
    _DEPRECATED_OPEN_IN_NEW_TAB = 'Open in New Tab'
    _OPEN_IN_NEW_TAB = ['Open in', 'New Tab']
    _MAXIMIZE_ITEM = 'Maximize Item'
    _RESTORE_ITEM = 'Restore Item'
    _IMAGE_ENHANCEMENT = 'Image Enhancement...'
    _ROTATE_TO = ['Rotate to']
    _ROTATE_TO_DEGREES = '{} degrees'

    # Test camera and Virtual camera scenes
    _RESOLUTION = [re.compile(r'Resolution[.]*')]
    _CAMERA_SETTINGS = 'Camera Settings...'

    # File scene only
    _CHECK_FILE_WATERMARK = 'Check File Watermark'
    _FILE_SETTINGS = 'File Settings...'

    def open_in_new_tab(self):
        if self._DEPRECATED_OPEN_IN_NEW_TAB in self.get_options():
            self.activate_items(self._DEPRECATED_OPEN_IN_NEW_TAB)
        else:
            self.activate_items(self._OPEN_IN_NEW_TAB)

    def maximize_item(self):
        self.activate_items(self._MAXIMIZE_ITEM)

    def restore_item(self):
        self.activate_items(self._RESTORE_ITEM)

    def open_image_enhancement(self) -> ImageEnhancementDialog:
        self.activate_items(self._IMAGE_ENHANCEMENT)
        return ImageEnhancementDialog(self._api, self._hid).wait_until_appears()

    def rotate_to_degrees(self, degrees: int):
        if degrees not in (0, 90, 180, 270):
            raise RuntimeError(
                f"Non-standard value of rotation: {degrees}. Has to be 0, 90, 180 or 270  degrees")
        menu_items = self._ROTATE_TO + [self._ROTATE_TO_DEGREES.format(degrees)]
        self.activate_items(*menu_items)

    def set_resolution(self, resolution):
        resolution = resolution.capitalize()
        if resolution not in ['Auto', 'Low', 'High']:
            raise RuntimeError(
                f"Non-standard resolution is set: {resolution}. Has to be Auto, Low or High")
        menu_items = self._RESOLUTION + [resolution]
        self.activate_items(*menu_items)

    def open_camera_settings(self) -> CameraSettingsDialog:
        self.activate_items(self._CAMERA_SETTINGS)
        return CameraSettingsDialog(self._api, self._hid).wait_until_appears()

    def open_check_watermark_dialog(self) -> CheckFileWatermarkDialog:
        self.activate_items(self._CHECK_FILE_WATERMARK)
        watermark = CheckFileWatermarkDialog(self._api, self._hid)
        watermark.wait_for_accessible()
        return watermark

    def open_file_settings(self) -> FileSettings:
        self.activate_items(self._FILE_SETTINGS)
        return FileSettings(self._api, self._hid).wait_until_appears()


class _BackgroundNotValid(Exception):
    pass
