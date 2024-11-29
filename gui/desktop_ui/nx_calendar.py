# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import date
from datetime import datetime
from typing import List

from gui.desktop_ui.media_capturing import CSSColor
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLabel
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class MonthCalendar:
    # month calendar

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = Widget(api, {
            "type": "TimelineCalendar",
            "visible": True,
            })
        self._next_month_button = Button(self._obj.find_child({
            "id": "forwardArrowButton",
            "visible": 1,
            }))
        self._prev_month_button = Button(self._obj.find_child({
            "id": "backArrowButton",
            "visible": 1,
            }))

    def show(self):
        _logger.info('%r: Show', self)
        TimelineControlWidget(self._api, self._hid).calendar_button.set(True)

    def _set_month_year(self, expected: datetime):
        expected = date(month=expected.month, year=expected.year, day=1)
        while True:
            selected_datetime = date(self._get_selected_year(), self._get_selected_month(), 1)
            if selected_datetime < expected:
                self._move_to_next_month()
            elif selected_datetime > expected:
                self._move_to_prev_month()
            else:
                break

    def _move_to_next_month(self):
        _logger.info('%r: Move to next month', self)
        month = self._get_selected_month()
        self._hid.mouse_left_click_on_object(self._next_month_button)
        time.sleep(.5)
        if not month != self._get_selected_month():
            raise RuntimeError("Calendar isn't switched to the next month")

    def _move_to_prev_month(self):
        _logger.info('%r: Move to previous month', self)
        month = self._get_selected_month()
        self._hid.mouse_left_click_on_object(self._prev_month_button)
        time.sleep(.5)
        if not month != self._get_selected_month():
            raise RuntimeError("Calendar isn't switched to the previous month")

    def _get_header_month_year(self):
        label = Widget(self._api, {
            'id': 'yearMonthLabel',
            'type': 'QQuickText',
            'visible': True,
            })
        [month, year] = QLabel(label).get_text().split()
        return month, year

    def _get_selected_month(self):
        [month, _] = self._get_header_month_year()
        return datetime.strptime(month, '%B').month

    def _get_selected_year(self):
        [_, year] = self._get_header_month_year()
        return int(year)

    def _month_days(self) -> List['_CalendarCell']:
        # objects of previous/next month are shown too
        # we collect only indexes between days with text 1 - they're inside the month
        _logger.info('%r: Get month days', self)
        # Looking for clickable cells only. Depends on available datetime period of the timeline.
        cells = self._obj.find_children({
            'id': 'calendarDay',
            'visible': True,
            'enabled': True,
            })
        day_cells = [_CalendarCell(cell, self._hid) for cell in cells]
        current_month_text_color = CSSColor('#e1e7ea')
        days = []
        for cell in day_cells:
            if cell.has_color(current_month_text_color):
                days.append(cell)
        return days

    def day_cell(self, date: datetime) -> '_CalendarCell':
        self._set_month_year(date)
        for d in self._month_days():
            if int(d.get_text()) == date.day:
                return d

    def wait_for_accessible(self):
        self._obj.wait_for_accessible()

    def wait_for_inaccessible(self):
        self._obj.wait_for_inaccessible()


class DayTimeCalendar:
    # day-time calendar

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = Widget(api, {
            'type': 'TimeSelector',
            'id': 'timeSelector',
            "visible": 1,
            })

    def _hours(self) -> List['_CalendarCell']:
        result = []
        cells = self._obj.find_children({
            'visible': True,
            'enabled': True,
            'id': 'hourItem',
            })
        for cell in cells:
            result.append(_CalendarCell(cell, self._hid))
        return result

    def hour_cell(self, date: datetime) -> '_CalendarCell':
        MonthCalendar(self._api, self._hid).day_cell(date).click()
        expected_hour = date.hour
        for i, hour_cell in enumerate(self._hours()):
            if i == expected_hour:
                return hour_cell


class _CalendarCell:
    # colors taken from
    # nx/open/vms/client/nx_vms_client_desktop/external_resources/skin/basic_colors.json
    INDICATION_TYPES_COLORS = {
        # Shade of green to indicate the archive belonging to the currently selected camera.
        'primary archive': CSSColor('#66BB6A'),
        # Shade of green to indicate the archive belonging to the camera that isn't currently selected.
        'secondary archive': CSSColor("#43A047"),
        }

    def __init__(self, cell: Widget, hid: HID):
        self._cell = cell
        self._hid = hid

    def wait_for_indication(self, indication_type: str):
        timeout = 3.0
        _logger.info('%r: Looking for indication: %s', self, indication_type)
        expected_color = self.INDICATION_TYPES_COLORS[indication_type]
        start = time.monotonic()
        while True:
            if self._cell.image_capture().has_color_rgb(expected_color):
                return True
            else:
                time.sleep(0.5)
                if time.monotonic() - start > timeout:
                    return False

    def has_color(self, color: CSSColor) -> bool:
        return self._cell.image_capture().has_color_rgb(color)

    def get_text(self):
        label = self._cell.find_child({
            'type': 'QQuickText',
            'visible': True,
            })
        return label.get_text()

    def click(self):
        _logger.info('%r: Click', self)
        self._hid.mouse_left_click_on_object(self._cell)
