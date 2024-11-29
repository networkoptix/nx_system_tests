# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from datetime import datetime
from datetime import timedelta
from functools import lru_cache
from typing import List
from typing import NamedTuple
from typing import Sequence

from gui.desktop_ui.dialogs.export_settings import ExportSettingsDialog
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.main_window import get_control_layer
from gui.desktop_ui.media_capturing import RGBColor
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QCheckableButton
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMenu
from gui.desktop_ui.wrappers import QPlainTextEdit
from gui.desktop_ui.wrappers import QSlider
from gui.desktop_ui.wrappers import ScrollBar
from gui.desktop_ui.wrappers import TimelineZoomButton
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _LivePreviewTooltip:

    def __init__(self, api: TestKit):
        self._obj = Widget(api, {
            "name": "LivePreviewTooltip",
            "type": "nx::vms::client::desktop::workbench::timeline::LivePreviewTooltip",
            "visible": 1,
            })

    def _get_date(self) -> datetime:
        # This method needs to be refactored because now there is no date in white tooltip.
        # https://networkoptix.atlassian.net/browse/SQ-992
        date_label = self._obj.find_child({
            'type': 'nx::vms::client::desktop::TextEditLabel',
            'unnamed': 1,
            'visible': 1,
            })
        return datetime.strptime(
            QPlainTextEdit(date_label).get_text(), '%A, %B %d, %Y')

    def _get_time(self) -> datetime:
        time_label = self._obj.find_child({
            'occurrence': 2,
            'type': 'nx::vms::client::desktop::TextEditLabel',
            'unnamed': 1,
            'visible': 1,
            })
        return datetime.strptime(
            QPlainTextEdit(time_label).get_text(), '%I:%M:%S %p')

    def get_date_time(self) -> datetime:
        _logger.info('%r: Getting datetime', self)
        return datetime.combine(self._get_date().date(), self._get_time().time())

    def is_accessible_timeout(self, timeout: float):
        self._obj.is_accessible_timeout(timeout)


class _Chunk(NamedTuple):
    start: int
    end: int


class _ColoredChunk:

    def __init__(self, left: int, right: int, color: RGBColor):
        self.color = color
        self._left = left
        self._right = right

    def concatenate(self, other: '_ColoredChunk'):
        if self._left - other._right > 1 or other._left - self._right > 1:
            raise ValueError(f"{self}: {other} is not adjacent")
        elif self._right < other._left:
            self._right = other._right
        elif other._right < self._left:
            self._left = other._left
        else:
            raise RuntimeError(f"{self}: Can't concatenate {other}")

    def extend(self):
        self._right += 1

    def right_neighbor(self, color: RGBColor) -> '_ColoredChunk':
        return self.__class__(self._right + 1, self._right + 1, color)

    def as_closed(self) -> _Chunk:
        return _Chunk(self._left, self._right)

    def __repr__(self):
        return f'{self.__class__}({self._left}, {self._right}, {self.color})'


class _ChunkedStripe:

    def __init__(self, chunks: Sequence[_ColoredChunk]):
        if not chunks:
            raise ValueError("A chunks sequence must at least one chunks long")
        self._chunks = chunks

    def dissolve(self, color: RGBColor) -> '_ChunkedStripe':
        result: List[_ColoredChunk] = []
        for chunk in self._chunks:
            try:
                last_chunk = result[-1]
            except IndexError:
                if chunk.color != color:
                    result.append(chunk)
                continue
            if chunk.color == color or chunk.color == last_chunk.color:
                last_chunk.concatenate(chunk)
            else:
                result.append(chunk)
        if self._chunks[0].color == color:
            result[0].concatenate(self._chunks[0])
        return self.__class__(result)

    def get_chunks(self, color: RGBColor) -> Sequence[_Chunk]:
        return [chunk.as_closed() for chunk in self._chunks if chunk.color == color]


def _make_stripe(colors: Sequence[RGBColor]) -> _ChunkedStripe:
    if not colors:
        raise ValueError("A colors sequence must be at least one pixel long")
    first_color, *rest_colors = colors
    result = [_ColoredChunk(0, 0, first_color)]
    for color in rest_colors:
        last_chunk = result[-1]
        if last_chunk.color == color:
            last_chunk.extend()
        else:
            result.append(last_chunk.right_neighbor(color))
    return _ChunkedStripe(result)


class Timeline:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def _get_object(self):
        return get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "yes",
            "movable": "no",
            "objectName": "TimeSlider",
            "selectable": "no",
            "type": "QnTimeSlider",
            "visible": "yes",
            })

    def wait_for_inaccessible(self):
        self._get_object().wait_for_inaccessible()

    def is_accessible(self):
        return self._get_object().is_accessible()

    def click(self):
        _logger.info('%r: Click', self)
        self._hid.mouse_left_click_on_object(self._get_object())

    def image_capture(self):
        return self._get_object().image_capture()

    def _get_navigation_item(self):
        return get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "yes",
            "movable": "no",
            "selectable": "no",
            "type": "QnNavigationItem",
            "visible": "yes",
            })

    def _get_scrollbar(self):
        scrollbar = self._get_navigation_item().find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "movable": "no",
            "selectable": "no",
            "type": "QnTimeScrollBar",
            "visible": "yes",
            })
        return ScrollBar(scrollbar)

    def get_page_step(self):
        return self._get_scrollbar().get_page_step()

    def get_current_length(self) -> timedelta:
        # Use scrollbar not timeline to determine current length.
        return timedelta(milliseconds=self.get_page_step())

    def _get_hide_timeline_button(self):
        button = get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "yes",
            "movable": "no",
            "selectable": "no",
            "toolTip": "Hide Timeline<b></b>",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            "occurrence": 1,
            })
        return Button(button)

    def is_open(self) -> bool:
        return self._get_hide_timeline_button().is_accessible()

    def show(self):
        _logger.info('%r: Show', self)
        if not self.is_open():
            show_timeline_button = get_control_layer(self._api).find_child({
                "acceptDrops": "no",
                "enabled": "yes",
                "focusable": "yes",
                "movable": "no",
                "selectable": "no",
                "toolTip": "Show Timeline<b></b>",
                "type": "QnImageButtonWidget",
                "visible": "yes",
                })
            self._hid.mouse_left_click_on_object(show_timeline_button)
            time.sleep(1)

    def hide(self):
        _logger.info('%r: Hide', self)
        if self.is_open():
            self._hid.mouse_left_click_on_object(self._get_hide_timeline_button())
            time.sleep(1)

    def _get_interval_rectangle(self, offset=0.0, width=1.0):
        offset, width = float(offset), float(width)

        if offset + width > 1 + 1e-6:
            raise RuntimeError('Incorrect interval parameters')

        bounds = self._get_object().bounds()
        interval_rectangle = ScreenRectangle(
            bounds.top_left().x + int(bounds.width * offset),
            bounds.top_left().y,
            int(bounds.width * width),
            bounds.height,
            )
        return interval_rectangle

    def _select_interval(self, offset=0.0, width=1.0):
        """Select timeline interval.

        To select an interval on timeline:
        1. find a rectangle of the interval;
        2. drag mouse cursor from the rectangle start to the rectangle end
               (along vertical middle line).
        We can set position of the interval by passing offset and width as float parts of 1.
        By default, the interval is all visible timeline.
        It is hard to get the exact beginning or end of timeline.
        For these cases we drag slightly excessively.
        """
        _logger.info('%r: Select interval: offset %s, width %s', self, offset, width)
        offset, width = float(offset), float(width)
        interval_rectangle = self._get_interval_rectangle(offset, width)

        # drop previous selected interval if it has been done
        self.click()
        time.sleep(1)

        if offset < 1e-6:  # float 0
            interval_start_coords = interval_rectangle.middle_right()
            # To select precisely from offset 0 we need to drag in the opposite direction
            # and slightly excessively.
            excess = int(interval_rectangle.width * 0.01)
            interval_finish_coords = interval_rectangle.middle_left().left(excess)
        else:
            interval_start_coords = interval_rectangle.middle_left()
            interval_finish_coords = interval_rectangle.middle_right()
        self._hid.mouse_drag_and_drop(interval_start_coords, interval_finish_coords)
        time.sleep(1)
        return interval_rectangle

    def activate_interval_context_item(self, interval_rectangle, item_text):
        _logger.info('%r: Open context menu', self)
        self._hid.mouse_right_click(
            interval_rectangle.bottom_center().up(int(interval_rectangle.height * 0.03)))
        QMenu(self._api, self._hid).activate_items(item_text)

    def activate_context_item(self, item_text):
        # Without selection or interval.
        self._hid.mouse_right_click_on_object(self._get_object())
        QMenu(self._api, self._hid).activate_items(item_text)

    def create_bookmark_from_interval_context_menu(
            self, name, description, tags, offset=0.0, width=1.0):
        _logger.info(
            '%r: Create bookmark: name %s, description %s, tags %s',
            self, name, description, tags)
        interval_rectangle = self._select_interval(offset, width)
        self.activate_interval_context_item(interval_rectangle, "Add Bookmark...")
        time.sleep(1)
        _BookmarkAddEditDialog(self._api, self._hid).set_values(name, description, tags)
        bookmark = _TimelineBookmark(interval_rectangle, self._api, self._hid)
        bookmark.wait_for_accessible(5)
        return bookmark

    def open_export_video_dialog_for_interval(self, offset=0.0, width=1.0) -> ExportSettingsDialog:
        _logger.info('%r: Open Export Video Dialog', self)
        interval_rectangle = self._select_interval(offset, width)
        self.activate_interval_context_item(interval_rectangle, "Export Video...")
        time.sleep(1)
        export_dialog = ExportSettingsDialog(self._api, self._hid)
        if not export_dialog.is_open():
            raise RuntimeError("Export dialog is not open")
        return export_dialog

    def open_preview_search_for_interval(self, offset=0.0, width=1.0):
        _logger.info('%r: Open preview search', self)
        interval_rectangle = self._select_interval(offset, width)
        self.activate_interval_context_item(interval_rectangle, "Preview Search...")

    def open_preview_search(self):
        _logger.info('%r: Open preview search', self)
        self.activate_context_item("Preview Search...")

    def click_at_offset(self, offset):
        _logger.info('%r: Click at offset: %s', self, offset)
        if offset == 0.0:
            raise RuntimeError(
                'Clicking the zero position may lead to a click outside an object.'
                ' Pass small offset to ensure clicking inside the object area')
        interval_rectangle = self._get_interval_rectangle(float(offset), 0)
        self._hid.mouse_left_click(interval_rectangle.center())

    def scroll_at_offset(self, offset):
        _logger.info('%r: Scroll at offset: %s', self, offset)
        interval_rectangle = self._get_interval_rectangle(float(offset), 0)
        self._hid.mouse_scroll(interval_rectangle.center(), 100)

    def count_archive_chunks(self):
        return len(self._find_archive_chunks())

    def _find_chunks_by_color(self, color: RGBColor) -> Sequence[_Chunk]:
        # This will not work if multiple items are open on the scene.
        # Capture the timeline.
        _logger.info('%r: Looking for archive chunks', self)
        image = self.image_capture()
        # Take 1 pixel thin strip.
        archive_strip = image.crop(
            0,
            image.get_width(),
            int(image.get_height() * 0.97),
            int(image.get_height() * 0.97) + 1,
            )

        # Find all archive chunks as continuous pieces of colorful pixels.
        # Stable when Timeline tooltip in the archive chunk.
        # Remember start-end point of each of those chunks in pixels relative to timeline.
        TIMELINE_TOOLTIP_COLORS = [RGBColor(225, 231, 234), RGBColor(229, 233, 235)]
        chunked_stripe = _make_stripe(archive_strip.get_row_colors(row_n=0))
        cleaned_chunked_stripe = chunked_stripe
        for tooltip_color in TIMELINE_TOOLTIP_COLORS:
            cleaned_chunked_stripe = cleaned_chunked_stripe.dissolve(tooltip_color)
        chunks = cleaned_chunked_stripe.get_chunks(color)
        _logger.info('%r: Archive chunks: %s', self, chunks)
        return chunks

    def _find_archive_chunks(self) -> Sequence[_Chunk]:
        archive_colors = [RGBColor(76, 175, 80), RGBColor(58, 145, 30)]
        for color in archive_colors:
            chunks = self._find_chunks_by_color(color)
            if chunks:
                return chunks
        return []

    def get_red_chunks(self) -> Sequence[_Chunk]:
        motion_colors = [RGBColor(229, 57, 53), RGBColor(170, 30, 30)]
        for color in motion_colors:
            chunks = self._find_chunks_by_color(color)
            if chunks:
                return chunks
        return []

    def get_analytics_archive_chunks(self):
        # RGBColor(255, 193, 7) - 6.0. RGBColor(255, 202, 40) - 6.1 and higher.
        analytic_archive_colors = [RGBColor(255, 193, 7), RGBColor(255, 202, 40)]
        for color in analytic_archive_colors:
            chunks = self._find_chunks_by_color(color)
            if chunks:
                return chunks
        return []

    def get_analytics_archive_chunks_within_timeout(self):
        start_time = time.monotonic()
        while True:
            chunks = self.get_analytics_archive_chunks()
            if chunks:
                return chunks
            # This enormous timeout is a temporary solution until VMS-42050 is fixed
            if time.monotonic() - start_time > 50:
                return []
            time.sleep(.1)

    def count_playable_chunks(self):
        count = 0
        if TimelinePlaceholder(self._api).is_visible():
            return count

        timeline_navigation = TimelineNavigation(self._api, self._hid)
        timeline_navigation.pause_and_to_begin()
        prev = Scene(self._api, self._hid).first_item_image()
        while True:
            timeline_navigation.to_end()
            time.sleep(1)
            curr = Scene(self._api, self._hid).first_item_image()
            if curr.is_similar_to(prev):
                break
            count += 1
            prev = curr
        return count

    def zoom_to_archive_chunk(self):
        _logger.info('%r: Zoom to archive chunk', self)
        chunks = self._find_archive_chunks()
        if len(chunks) > 1:
            raise NotImplementedError()
        if len(chunks) == 0:
            raise RuntimeError('No chunks to zoom to')

        left, right = chunks[0]
        margin = 10
        bounds = self._get_object().bounds()

        def is_chunk_zoomed():
            return left < margin and bounds.width - right < margin

        while not is_chunk_zoomed():
            chunk = self._find_archive_chunks()[0]
            left, right = chunk
            if left > (bounds.width - right):
                self.scroll_at_offset(right / bounds.width)
            else:
                self.scroll_at_offset(left / bounds.width)
            time.sleep(1)

    def show_chunk_preview_tooltip(self) -> _LivePreviewTooltip:
        # Zoom chunk if it's hidden on timeline or LivePreviewTooltip is hidden by TimelineTooltip
        _logger.info('%r: Show chunk preview tooltip', self)
        left = 0
        right = 0
        margin = 10
        rectangle = self._get_object().bounds()
        start = time.monotonic()
        while left > margin or rectangle.width - right > margin:
            chunks = self._find_archive_chunks()
            if len(chunks) != 0:
                left, right = chunks[0]

                # show LivePreviewTooltip
                self._hid.mouse_move(rectangle.top_left().right(right).down(10))
                if _LivePreviewTooltip(self._api).is_accessible_timeout(1):
                    return _LivePreviewTooltip(self._api)

            if left > (rectangle.width - right):
                self.zoom_out_using_minus_button()
            else:
                self.zoom_in_using_plus_button()
            if time.monotonic() - start > 60:
                raise RuntimeError('Looking for chunk preview failed')
            time.sleep(1)

    def _get_zoom_button(self, locator: dict):
        return TimelineZoomButton(
            self._get_navigation_item().find_child(locator),
            self._hid,
            )

    def zoom_in_using_plus_button(self):
        _logger.info("%r: Zoom in using plus button", self)
        zoom_in_button = self._get_zoom_button({
            "objectName": "TimelineZoomInButton",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        zoom_in_button.click()
        time.sleep(1)

    def zoom_out_using_minus_button(self):
        _logger.info("%r: Zoom in using minus button", self)
        zoom_out_button = self._get_zoom_button({
            "objectName": "TimelineZoomOutButton",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        zoom_out_button.click()
        time.sleep(1)

    def zoom_out_by_double_click(self):
        _logger.info('%r: Zoom out by double click', self)
        self._hid.mouse_double_click_on_object(self._get_scrollbar())
        time.sleep(1)

    def verify_preview_search_period(
            self, expected_period: timedelta, items_limit: int = 0):
        # Click in turn on each scene item except first and verify that consecutive timedelta
        # is equal to expected.
        # Verify certain quantity of scene items if items limit is set.
        prev_datetime = None
        for item in Scene(self._api, self._hid).items_visually_ordered()[1:]:
            if items_limit > 0:
                # Activate and magnify.
                self._hid.mouse_left_click_on_object(item)
                curr_datetime = TimelineTooltip(self._api).date_time()
                if prev_datetime:
                    period_between_previews = curr_datetime - prev_datetime
                    tolerance = timedelta(seconds=1)
                    if not abs(period_between_previews - expected_period) < tolerance:
                        raise RuntimeError(
                            "Actual period doesn't match the expected one.\n"
                            f"Expected period: {expected_period}\n"
                            f"Actual period: {period_between_previews}")
                prev_datetime = curr_datetime
                # Deactivate and minify.
                self._hid.mouse_left_click_on_object(item)
                items_limit -= 1


class TimelinePlaceholder:
    # For live camera without archive TimelinePlaceholder is displayed instead of Timeline.

    def __init__(self, api: TestKit):
        self._api = api

    def _get_object(self):
        return get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "focusable": "no",
            "movable": "no",
            "selectable": "no",
            "type": "QnTimelinePlaceholder",
            })

    def get_camera_name(self):
        return self._get_object().get_text()

    def is_accessible_timeout(self, timeout: float):
        self._get_object().is_accessible_timeout(timeout)

    def is_enabled(self):
        return self._get_object().is_enabled()

    def is_visible(self):
        return self._get_object().is_visible()


class _BookmarkAddEditDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._tags_line_edit = QLineEdit(hid, Widget(api, {
            "name": "tagsLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))
        self._api = api
        self._hid = hid
        self._widget = Widget(self._api, {
            "name": "QnCameraBookmarkDialog",
            "type": "QnCameraBookmarkDialog",
            "visible": 1,
            })

    def set_values(self, name, description, tags):
        _logger.info(
            '%r: Create bookmark: Name %s, description %s, tags %s',
            self, name, description, tags)
        name_line_edit = self._widget.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        QLineEdit(self._hid, name_line_edit).type_text(name)
        # Description may have html tags, when using setText, text will be styled and tags removed.
        # setPlainText behavior here corresponds to user's behavior of typing or inserting text.
        description_line_edit = self._widget.find_child({
            "type": "QTextEdit",
            "unnamed": 1,
            "visible": 1,
            })
        QPlainTextEdit(description_line_edit).type_text(description)
        # Using setText with target value here somehow doesn't save the tags.
        self._tags_line_edit.type_text(tags)
        ok_button = self._widget.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._widget.wait_for_inaccessible(5)


class _TimelineBookmark:
    """Bookmark that is displayed on the timeline and its tooltip."""

    def __init__(self, rectangle, api: TestKit, hid: HID):
        self.rectangle = rectangle
        self._api = api
        self._hid = hid

    @lru_cache()
    def _get_tooltip(self) -> Widget:
        locator_6_0 = {
            "type": "nx::vms::client::desktop::workbench::timeline::BookmarkTooltip",
            "unnamed": 1,
            "visible": 1,
            }
        locator_6_1 = {
            "type": "BookmarkTooltip",
            "unnamed": 1,
            "visible": 1,
            }
        tooltip = Widget(self._api, locator_6_1)
        # For backward compatibility with VMS 6.0
        if not tooltip.is_accessible_timeout(0):
            tooltip = Widget(self._api, locator_6_0)
        return tooltip

    def __repr__(self):
        return f'{self.__class__.__name__}({self.rectangle})'

    def activate_context_menu_item(self, item):
        Timeline(self._api, self._hid).activate_interval_context_item(self.rectangle, item)

    def exists(self):
        self.hover_for_tooltip()
        return self._get_tooltip().is_accessible()

    def hover_for_tooltip(self):
        _logger.info('%r: Hover away', self)
        MainWindow(self._api, self._hid).hover_away()
        time.sleep(1)  # Let previous one disappear when moving fast between bookmarks.
        _logger.info('%r: Hover', self)
        self._hid.mouse_move(self.rectangle.bottom_center().up(int(self.rectangle.height * 0.1)))
        time.sleep(1)  # Let previous one disappear when moving fast between bookmarks.

    def delete_using_tooltip(self):
        _logger.info('%r: Delete using tooltip', self)
        self.hover_for_tooltip()
        locator_6_0 = {
            "objectName": "BookmarkTooltipDeleteButton",
            "type": "QPushButton",
            "visible": 1,
            "enabled": 1,
            }
        locator_6_1 = {
            "source": re.compile("skin/20x20/Solid/delete.svg"),
            "type": "Image",
            "visible": 1,
            "enabled": 1,
            }
        button = self._get_tooltip().find_child(locator_6_1)
        # For backward compatibility with VMS 6.0
        if not button.is_accessible_timeout(0):
            button = self._get_tooltip().find_child(locator_6_0)
        self._hid.mouse_left_click_on_object(button)
        MessageBox(self._api, self._hid).close_by_button('Delete')

    def remove_using_context_menu(self):
        _logger.info('%r: Remove using context menu', self)
        self.activate_context_menu_item('Delete Bookmark...')
        MessageBox(self._api, self._hid).close_by_button('Delete')

    def open_export_bookmark_dialog(self) -> ExportSettingsDialog:
        _logger.info('%r: Open Export Bookmark Dialog', self)
        self.activate_context_menu_item('Export Bookmark...')
        return ExportSettingsDialog(self._api, self._hid)

    def open_export_bookmark_dialog_using_tooltip(self) -> ExportSettingsDialog:
        _logger.info('%r: Open Export Bookmark Dialog using tooltip', self)
        self.hover_for_tooltip()
        locator_6_0 = {
            "objectName": "BookmarkTooltipExportButton",
            "type": "QPushButton",
            "visible": 1,
            "enabled": 1,
            }
        locator_6_1 = {
            "source": re.compile("skin/20x20/Solid/download.svg"),
            "type": "Image",
            "visible": 1,
            "enabled": 1,
            }
        button = self._get_tooltip().find_child(locator_6_1)
        # For backward compatibility with VMS 6.0
        if not button.is_accessible_timeout(0):
            button = self._get_tooltip().find_child(locator_6_0)
        self._hid.mouse_left_click_on_object(button)
        return ExportSettingsDialog(self._api, self._hid)

    def edit_using_tooltip(self, name, description, tags):
        _logger.info('%r: Edit using tooltip', self)
        self.hover_for_tooltip()
        locator_6_0 = {
            "objectName": "BookmarkTooltipEditButton",
            "type": "QPushButton",
            "visible": 1,
            "enabled": 1,
            }
        locator_6_1 = {
            "source": re.compile("skin/20x20/Solid/edit.svg"),
            "type": "Image",
            "visible": 1,
            "enabled": 1,
            }
        button = self._get_tooltip().find_child(locator_6_1)
        # For backward compatibility with VMS 6.0
        if not button.is_accessible_timeout(0):
            button = self._get_tooltip().find_child(locator_6_0)
        self._hid.mouse_left_click_on_object(button)
        _BookmarkAddEditDialog(self._api, self._hid).set_values(name, description, tags)

    def _get_bookmark_tooltip_with_text(self, text):
        locator = {
            "enabled": 1,
            "visible": 1,
            "text": text,
            }
        label = self._get_tooltip().find_child({
            "type": "QQuickText",
            **locator,
            })
        # For backward compatibility with VMS 6.0
        if not label.is_accessible_timeout(0):
            label = self._get_tooltip().find_child({
                "type": "QLabel",
                **locator,
                })
        return QLabel(label)

    def _get_tags_button_with_text(self, text: str):
        button_locator = {
            "enable": 1,
            "visible": 1,
            "text": text,
            }
        button = self._get_tooltip().find_child({
            "id": "label",
            **button_locator,
            })
        # For backward compatibility with VMS 6.0
        if not button.is_accessible_timeout(0):
            button = self._get_tooltip().find_child({
                "type": "QPushButton",
                "name": "BookmarkTooltipTagButton",
                **button_locator,
                })
        return Button(button)

    def verify(self, name, description, tags):
        self.hover_for_tooltip()
        bookmark_tooltip = self._get_bookmark_tooltip_with_text(name)
        bookmark_tooltip.wait_for_accessible(timeout=5)

        bookmark_tooltip = self._get_bookmark_tooltip_with_text(description)
        bookmark_tooltip.wait_for_accessible(timeout=5)

        tags_button = self._get_tags_button_with_text(tags)
        tags_button.wait_for_accessible(timeout=5)

    def wait_for_accessible(self, timeout: float = 3):
        self.hover_for_tooltip()
        self._get_tooltip().wait_for_accessible(timeout=timeout)


class TimelineTooltip:
    """Tooltip that appears when the timeline is clicked.

    Contains time at the clicked position.
    """

    def __init__(self, api: TestKit):
        self._obj = Widget(api, {
            "id": "timeMarker",
            "type": "TimeMarker",
            "unnamed": 1,
            "visible": True,
            })

    def time(self, fmt='%I:%M:%S %p') -> datetime:
        """If the timeline zoomed in is close to the maximum, then the time format will change."""
        value = str(self._obj.wait_property('timeText'))
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            zoomed_fmt = '%I:%M:%S.%f %p'
            return datetime.strptime(value, zoomed_fmt)

    def date_time(self) -> datetime:
        # We get timestamp from Epoch in milliseconds. Requires value in seconds.
        timestamp = self._obj.wait_property('timestampMs') / 1000
        return datetime.fromtimestamp(timestamp)

    def verify_datetime(
            self,
            expected: datetime,
            tolerance=timedelta(seconds=0),
            ):
        actual = self.date_time()
        _logger.debug('timeline tooltip time: %s', actual.isoformat(timespec='milliseconds'))
        _logger.debug('expected time: %s', expected.isoformat(timespec='milliseconds'))
        _logger.debug('tolerance: %s', tolerance)
        if actual.replace(microsecond=0) - expected.replace(microsecond=0) > tolerance:
            raise RuntimeError(
                "Actual datetime doesn't match the expected one.\n "
                f"Actual: {actual}, expected: {expected}")

    def wait_for_datetime(
            self,
            expected: datetime,
            tolerance=timedelta(seconds=0),
            timeout: float = 2,
            ):
        _logger.info(
            '%r: Wait for datetime: %s. Timeout: %s second(s)',
            self, expected, timeout)
        start_time = time.monotonic()
        while True:
            try:
                self.verify_datetime(expected, tolerance)
                return
            except RuntimeError as e:
                if "Actual datetime doesn't match the expected one." in str(e):
                    if time.monotonic() - start_time > timeout:
                        raise e
                    continue
            time.sleep(.5)


class TimelineNavigation:

    def __init__(self, api: TestKit, hid: HID):
        self._hid = hid
        self._play_pause_button = QCheckableButton(hid, Widget(api, {
            "name": "Play",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._to_beginning_prev_chunk_button = Button(Widget(api, {
            "name": "To Start",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._to_end_next_chunk_button = Button(Widget(api, {
            "name": "To End",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._prev_frame_speed_down_button = Button(Widget(api, {
            "name": "Previous Frame",
            "type": "QPushButton", "visible": 1,
            }))
        self._next_frame_speed_up_button = Button(Widget(api, {
            "name": "Next Frame",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._button_mapping = {
            'Pause': self._play_pause_button,
            'Play': self._play_pause_button,
            'Speed Down': self._prev_frame_speed_down_button,
            'Previous Frame': self._prev_frame_speed_down_button,
            'Speed Up': self._next_frame_speed_up_button,
            'Next Frame': self._next_frame_speed_up_button,
            'Previous Chunk': self._to_beginning_prev_chunk_button,
            'Next Chunk': self._to_end_next_chunk_button,
            }

    def button_is_enabled(self, button_key):
        button = self._button_mapping[button_key]
        return button.is_accessible() and button_key in button.tooltip()

    def play(self):
        _logger.info("%r: Play", self)
        self._play_pause_button.set(True)

    def pause_and_to_begin(self):
        self.pause()
        self.to_beginning()

    def pause(self):
        _logger.info("%r: Pause", self)
        self._play_pause_button.set(False)
        # Wait for the video to stop playing.
        time.sleep(2)

    def get_playback_button_tooltip_text(self):
        return self._play_pause_button.tooltip()

    def wait_for_pause_icon(self, timeout: float = 1):
        _logger.info('%r: Wait for pause icon. Timeout: %s second(s)', self, timeout)
        start_time = time.monotonic()
        while True:
            if self._play_pause_button.is_checked():
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError("Button has Play icon")
            time.sleep(.1)

    def to_prev_chunk(self):
        _logger.info("%r: To previous chunk", self)
        self._hid.mouse_left_click_on_object(self._to_beginning_prev_chunk_button)

    def to_beginning(self):
        _logger.info("%r: To beginning", self)
        self._hid.mouse_left_click_on_object(self._to_beginning_prev_chunk_button)

    def to_next_chunk(self):
        _logger.info("%r: To next chunk", self)
        self._hid.mouse_left_click_on_object(self._to_end_next_chunk_button)

    def to_end(self):
        _logger.info("%r: To end", self)
        self._hid.mouse_left_click_on_object(self._to_end_next_chunk_button)

    def to_previous_frame(self):
        _logger.info("%r: To previous frame", self)
        self._hid.mouse_left_click_on_object(self._prev_frame_speed_down_button)
        # Wait for the video to change on screen.
        time.sleep(1)

    def to_next_frame(self):
        _logger.info("%r: To next frame", self)
        self._hid.mouse_left_click_on_object(self._next_frame_speed_up_button)
        # Wait for the video to change on screen.
        time.sleep(1)

    def increase_speed_2x(self):
        _logger.info("%r: Increase speed", self)
        self._hid.mouse_left_click_on_object(self._next_frame_speed_up_button)

    def lower_speed_2x(self):
        _logger.info("%r: Decrease speed", self)
        self._hid.mouse_left_click_on_object(self._prev_frame_speed_down_button)


class TimelineControlWidget:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self.mute_button = QCheckableButton(hid, Widget(api, {
            "name": "Toggle Mute",
            "type": "QPushButton",
            "visible": 1,
            }))
        self.live_button = QCheckableButton(hid, Widget(api, {
            "name": "Jump to Live",
            "type": "QPushButton",
            "visible": 1,
            }))
        self.synchronize_streams_button = QCheckableButton(hid, Widget(api, {
            "name": "Synchronize Streams",
            "type": "QPushButton",
            "visible": 1,
            }))
        self.calendar_button = QCheckableButton(hid, Widget(api, {
            "name": "Hide Calendar",
            "type": "QPushButton",
            "visible": 1,
            }))
        self.volume_slider = _TimelineVolumeSlider(api)

    def wait_for_live_button_unchecked(self, timeout: float = 3):
        _logger.info(
            '%r: Wait for live button becomes uncheck. Timeout: %s second(s)',
            self, timeout)
        start_time = time.monotonic()
        while True:
            if not self.live_button.is_checked():
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError("Timeout: Live button is still checked")
            time.sleep(.1)


class _TimelineVolumeSlider(QSlider):

    def __init__(self, api: TestKit):
        _obj = Widget(api, {
            "type": "nx::vms::client::desktop::workbench::timeline::VolumeSlider",
            "unnamed": 1,
            "visible": 1,
            })
        super().__init__(_obj)

    def is_muted(self):
        return self._widget.wait_property('muted')
