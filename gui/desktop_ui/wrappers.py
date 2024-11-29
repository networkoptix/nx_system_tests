# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import re
import time
from enum import Enum
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Union

from gui import testkit
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.testkit import ObjectAttributeNotFound
from gui.testkit.hid import ClickableObject
from gui.testkit.hid import ControlModifier
from gui.testkit.hid import HID
from gui.testkit.hid import ShiftModifier
from gui.testkit.hid import validate_typed_text
from gui.testkit.testkit import TestKit
from gui.testkit.testkit import _Object

_logger = logging.getLogger(__name__)


class ScrollBar(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def _is_at_maximum(self):
        return self._widget.wait_property('sliderPosition') == self._widget.wait_property('maximum')

    def get_current_position(self) -> int:
        return int(self._widget.wait_property('sliderPosition'))

    def scroll_to_position(self, position: int):
        self._widget.wait_for_object().call_method('setValue', position)

    def scroll_page(self):
        self.scroll_to_position(self.get_current_position() + self.get_page_step())

    def reset(self):
        self.scroll_to_position(0)

    def is_accessible(self):
        return self._widget.is_accessible_timeout(3)

    def scroll_to_object(self, item):
        # Scroll from beginning until item is accessible.
        if self.is_accessible():
            self.reset()
            while not item.is_accessible() and not self._is_at_maximum():
                self.scroll_page()
        if not item.is_accessible():
            raise RuntimeError("Object is not accessible")

    def get_page_step(self):
        return self._widget.wait_property('pageStep')


class QmlScrollBar(ScrollBar):
    # This is a basic wrapper over Qml version of ScrollBar.
    # Tried to keep the same interface.

    def _is_at_maximum(self):
        end_position = self.get_current_position() + self._widget.wait_property('size')
        return abs(end_position - 1) < 1e-6

    def get_current_position(self) -> float:
        return self._widget.wait_property('position')

    def scroll_page(self):
        self._widget.wait_for_object().call_method('scrollBySteps', 1)

    def reset(self):
        self.scroll_to_position(0.0)

    def scroll_to_position(self, position: float):
        direction = 1 if position > self.get_current_position() else -1
        while not abs(self.get_current_position() - position) < 1e-6:
            self._widget.wait_for_object().call_method('scrollBySteps', direction)


class Checkbox:

    def __init__(self, hid: HID, widget: Widget):
        self._widget = widget
        self._hid = hid

    def set(self, value: bool):
        # Clicking at x center won't work for some checkboxes because they're too long
        if self.is_checked() != value:
            self._hid.mouse_left_click(self._widget.bounds().middle_left().right(10))
            start = time.monotonic()
            while True:
                if self.is_checked() == value:
                    return
                if time.monotonic() - start > 1:
                    raise RuntimeError('Checkbox state value not changed')
                time.sleep(.1)

    def click(self):
        self._hid.mouse_left_click(self._widget.bounds().middle_left().right(10))

    def is_checked(self) -> bool:
        return self._widget.wait_property('checked')

    def get_text(self):
        return str(self._widget.wait_property('text'))

    def is_accessible(self):
        return self.is_accessible_timeout(3)

    def is_accessible_timeout(self, timeout: float):
        # Timeout in seconds.
        try:
            self._widget.wait_for_object(timeout)
            return True
        except testkit.ObjectNotFound:
            return False

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)

    def image_capture(self):
        return self._widget.image_capture()

    def hover(self):
        self._hid.mouse_move(self._widget.center())

    def is_enabled(self):
        return self._widget.is_enabled()

    def bounds(self):
        return self._widget.bounds()


class Button(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def get_text(self):
        return self._widget.get_text()

    def tooltip(self):
        try:
            return self._widget.wait_property('toolTip')
        except testkit.ObjectAttributeNotFound:
            raise RuntimeError('Button does not have tooltip')

    def is_enabled(self):
        return self._widget.is_enabled()

    def is_enabled_timeout(self, timeout: float):
        return self._widget.is_accessible_timeout(timeout)

    def is_accessible(self):
        return self._widget.is_accessible()

    def is_accessible_timeout(self, timeout: float):
        return self._widget.is_accessible_timeout(timeout)

    def wait_for_accessible(self, timeout: float = 5):
        return self._widget.wait_for_accessible(timeout)

    def wait_for_inaccessible(self, timeout: float = 5):
        return self._widget.wait_for_inaccessible(timeout)

    def image_capture(self):
        return self._widget.image_capture()

    def bounds(self):
        return self._widget.bounds()

    def center(self) -> ScreenPoint:
        return self._widget.center()


class QCheckableButton(Button, Checkbox):

    def __init__(self, hid: HID, widget: Widget):
        super().__init__(widget)
        self._hid = hid

    def set_checked(self, value):
        # Set checked by Qt object method.
        # Be sure that object has a setChecked method.
        self._widget.wait_for_object().call_method('setChecked', value)


class QLine:

    def __init__(self, widget: Widget):
        self._widget = widget

    def get_text(self) -> str:
        return self._widget.get_text()


class QLineEdit(QLine):

    def __init__(self, hid: HID, widget: Widget):
        super().__init__(widget)
        self._hid = hid

    def __repr__(self):
        return f'<QLineEdit: {self._widget}>'

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)

    def is_accessible(self):
        return self._widget.is_accessible_timeout(3)

    def get_width(self):
        return self._widget.bounds().width

    def type_text(self, text: str, need_activate: bool = True):
        self.clear_field()
        _logger.debug('Type text "%s" to field %r', text, self)
        if need_activate:
            # There are objects with a constant suffix ('%', 'cells' and so on).
            # Click the beginning of object for correct typing.
            obj_bounds = self._widget.bounds()
            self._hid.mouse_left_click(obj_bounds.top_left().right(5).down(obj_bounds.height // 2))
        self._hid.write_text(text)
        self.wait_for_text(text)

    def clear_field(self, timeout: float = 3):
        _logger.debug(
            'Waiting for clear field in object %r. Timeout %s second(s)',
            self, timeout)
        obj = self._widget.wait_for_object()
        start_time = time.monotonic()
        while True:
            obj.call_method('clear')
            widget_text = self.get_text()
            if widget_text in ['', '%', ' cells', '---', ' s']:
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(
                    f"Clear field {self!r} timed out! Text in field: {widget_text!r}")
            time.sleep(.1)

    def set_text_without_validation(self, text: str):
        """Set text by Qt function.

        There are some places in client where QLineEdit has pre-validation of
        text. Simple typing can be unsuccessful in this case. It is not "human"
        like solution so this is workaround.
        More: https://doc.qt.io/qt-6/qlineedit.html#text-prop
        """
        _logger.debug('Type text "%s" to field %r', text, self)
        self._widget.wait_for_object().call_method('setText', text)

    def is_active(self) -> bool:
        return bool(self._widget.wait_property('active'))

    def click(self):
        self._hid.mouse_left_click_on_object(self._widget)

    def wait_for_text(self, text: str, timeout: float = 3):
        _logger.debug(
            'Waiting for object %r has a text "%s". Timeout %s second(s)',
            self, text, timeout)
        start_time = time.monotonic()
        while True:
            widget_text = self._widget.get_text()
            if widget_text == text:
                return
            if text in widget_text:
                _, extra_text = widget_text.split(text)
                if extra_text in ('%', ' cells'):
                    return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"{self!r} has no text: {text!r}!")
            time.sleep(.1)

    def is_enabled(self) -> bool:
        return self._widget.is_enabled()

    def is_accessible_timeout(self, timeout_sec: float) -> bool:
        return self._widget.is_accessible_timeout(timeout_sec)


class NumberInput:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def type_number(self, number: float):
        obj_bounds = self._widget.bounds()
        self._hid.mouse_left_click(obj_bounds.middle_left().right(5))
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.keyboard_hotkeys('Backspace')
        self._hid.write_text(str(number))

    def get_value(self):
        try:
            return self._widget.wait_property('value', 0)
        except ObjectAttributeNotFound:
            return None


class QPlainTextEdit(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def get_text(self):
        value = self._widget.wait_property('plainText')
        if value is not None:
            return str(value)
        return None

    def type_text(self, text: str, **_):
        self._widget.wait_for_object().call_method('setPlainText', text)

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class ComboBox:

    def __init__(self, hid: HID, widget: Widget):
        self._widget = widget
        self._hid = hid

    def open(self):
        self._hid.mouse_left_click_on_object(self._widget)
        time.sleep(1)

    def current_item(self) -> str:
        return str(self._widget.wait_property('currentText'))

    def select(self, item_text: str):
        if item_text != self.current_item():
            self.open()
            self._hid.mouse_left_click_on_object(self.get_item(item_text))

    def select_by_right_arrow(self, item_text: str):
        if item_text != self.current_item():
            # Click with a little shift to the left to be sure that the area is inside the object
            self._hid.mouse_left_click(self._widget.bounds().middle_right().left(10))
            item = self._widget.find_child({
                'type': 'QModelIndex',
                'text': item_text,
                })
            self._hid.mouse_left_click_on_object(item)

    def get_list(self) -> List:
        items = self._widget.find_children({'type': 'QModelIndex'})
        return [item.wait_property('text', timeout=0) for item in items]

    def is_accessible(self):
        return self._widget.is_accessible_timeout(3)

    def is_accessible_timeout(self, timeout_sec: float) -> bool:
        return self._widget.is_accessible_timeout(timeout_sec)

    def get_item(self, item_text: str) -> Widget:
        item = self._widget.find_child({
            'type': 'QModelIndex',
            'text': item_text,
            })
        return item

    def get_list_view(self, locator: dict) -> Widget:
        return self._widget.find_child(locator)


class EditableComboBox(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class QMLComboBox:

    def __init__(self, widget: Widget):
        self._widget = widget

    def current_item(self) -> str:
        return str(self._widget.wait_property('currentText'))

    def select(self, value: str):
        combobox = self._widget.wait_for_object()
        index = combobox.call_method('findText', value)
        if index == -1:
            raise RuntimeError(f'Combobox has no value: {value}')
        combobox.call_method('setCurrentIndex', index)


class QMLComboBoxIncremental:

    def __init__(self, widget: Widget):
        self._widget = widget

    def current_item(self) -> str:
        return str(self._widget.wait_property('currentText'))

    def select(self, value: str):
        combobox = self._widget.wait_for_object()
        index = combobox.call_method('find', value)
        if index == -1:
            raise RuntimeError(f'Combobox has no value: {value}')
        while index != combobox.get_attr('currentIndex'):
            if combobox.get_attr('currentIndex') > index:
                combobox.call_method('decrementCurrentIndex')
            else:
                combobox.call_method('incrementCurrentIndex')


class EditableQMLComboBox(QMLComboBox):

    # This beast combines LineEdit logic of setting an arbitrary value and Combobox logic of
    # choosing value from a list of available values.
    def set_text(self, value: str):
        self._widget.wait_for_object().set_attr('editText', value)


class BaseWindow(Widget):

    def __init__(self, api: TestKit, locator_or_obj: Union[dict, _Object]):
        super().__init__(api, locator_or_obj)

    def wait_for_object(self, timeout: float = 20) -> _Object:
        _logger.debug(
            'Waiting for object %s. Timeout: %s second(s)',
            self._locator or self._obj, timeout)
        start = time.monotonic()
        while True:
            try:
                if not self.wait_property('visible', 0):
                    raise testkit.ObjectAttributeValueError(
                        f'Object {self._locator or self._obj!r} is not visible')
                break
            except (
                    testkit.ObjectAttributeValueError,
                    testkit.ObjectAttributeNotFound,
                    ) as e:
                if time.monotonic() - start > timeout:
                    raise testkit.ObjectNotFound(e)
            time.sleep(.1)
        return self._get_obj()

    def activate(self):
        self.wait_for_object().call_method('activateWindow')

    def wait_until_appears(self, timeout: float = 10):
        self.wait_for_accessible(timeout)
        return self

    def wait_until_closed(self, timeout: float = 10):
        self.wait_for_inaccessible(timeout)

    def close(self):
        _logger.debug('Close %s by Qt event', self.__class__.__name__)
        self._api.execute_function('testkit.post', self.wait_for_object(), 'QCloseEvent')
        self.wait_until_closed()

    def is_open(self):
        return self.is_accessible()

    def get_window_title(self):
        return str(self.wait_property('windowTitle'))


class QLabel(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def get_text(self):
        self.wait_for_accessible()
        return self._widget.get_text()

    def is_accessible(self):
        return self._widget.is_accessible_timeout(3)

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)

    def wait_for_inaccessible(self, timeout: float = 3):
        self._widget.wait_for_inaccessible(timeout)

    def bounds(self):
        return self._widget.bounds()


class EditableLabel(QLabel):

    def __init__(self, hid: HID, widget: Widget):
        super().__init__(widget)
        self._hid = hid

    def type_text(self, text: str):
        self._hid.mouse_left_click(self._widget.bounds().middle_left().right(5))
        validate_typed_text(text)
        self._widget.wait_for_object().call_method('setText', text)


class _MenuItem:

    def __init__(self, widget: Widget):
        self._widget = widget
        self.text = self._widget.wait_property('text', timeout=0)

    @property
    def checked(self) -> bool:
        try:
            return bool(self._widget.wait_property('checked', timeout=0))
        except testkit.ObjectAttributeNotFound:
            return False

    @property
    def enabled(self) -> bool:
        try:
            return bool(self._widget.wait_property('enabled', timeout=0))
        except testkit.ObjectAttributeNotFound:
            return False


class QMenu:

    def __init__(self, api: TestKit, hid: HID):
        self._menu_locator = {
            "type": "QMenu",
            "unnamed": 1,
            "visible": 1,
            "occurrence": 1,
            }
        self._widget = Widget(api, self._menu_locator)
        self._api = api
        self._hid = hid

    def activate_items(self, *item_names, timeout: float = 3):
        # This method allows activating chain of menus
        # by passing an arbitrary number of item names.
        _logger.info(
            '%r: Activate context menu item(s): %s',
            self, item_names)
        parent = self._menu_locator
        for name in item_names:
            parent_widget = Widget(self._api, parent)
            item = parent_widget.find_child({'text': name}, timeout=timeout)
            self._hid.mouse_left_click_on_object(item)
            new_item = {**parent, 'title': name}
            if parent.get('window', None):
                new_item['window'] = parent['window']
            parent = new_item

    @staticmethod
    def _find_options(obj: Widget) -> List[_MenuItem]:
        actions = obj.find_children({'unnamed': 1, 'visible': True})
        return [
            _MenuItem(action) for action in actions
            if action.wait_property('text', timeout=0)]

    def get_options(self) -> Mapping[str, _MenuItem]:
        items = {}
        for action in self._find_options(self._widget):
            items[action.text] = action
        return items

    def get_submenu_options(self, submenu_item: str) -> Mapping[str, _MenuItem]:
        items = {}
        submenu_widget = Widget(self._api, {
            **self._menu_locator,
            'title': submenu_item,
            })
        for action in self._find_options(submenu_widget):
            items[action.text] = action
        return items

    def close(self):
        self._hid.keyboard_hotkeys('Escape')
        time.sleep(.5)

    def is_accessible_timeout(self, timeout: float):
        return self._widget.is_accessible_timeout(timeout)

    def is_accessible(self):
        return self.is_accessible_timeout(3)

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)


class QQuickPopupItem:
    # QML counterpart for QMenu

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def _get_option_objects(self):
        # TODO: Fix search of QML objects inside Welcome Screen.
        menu_items = self._widget.find_children({
            "type": "MenuItem",
            "visible": True,
            })
        compact_menu_items = self._widget.find_children({
            "type": "CompactMenuItem",
            "visible": True,
            })
        return menu_items + compact_menu_items

    def get_options(self) -> List[str]:
        return [item.get_text() for item in self._get_option_objects()]

    def activate_item(self, item_name: Union[str, re.Pattern]):
        if not isinstance(item_name, re.Pattern):
            item_name = re.compile(item_name)

        for option_obj in self._get_option_objects():
            if item_name.search(option_obj.get_text()):
                self._hid.mouse_left_click_on_object(option_obj)
                break
        else:
            raise RuntimeError(f'Option {item_name} not found in menu')

    def wait_for_accessible(self, timeout: float = 1):
        self._widget.wait_for_accessible(timeout)


class QTable:
    # nx::vms::client::desktop::TableView

    def __init__(self, hid: HID, widget: Widget, columns):
        self._hid = hid
        self._widget = widget
        self._columns = columns

    def _get_model(self):
        return self._widget.wait_for_object().call_method('model')

    def header_bounds(self, header_text: str) -> Optional[ScreenRectangle]:
        try:
            header_index = self.json_model.get('headers', []).index(header_text)
        except ValueError:
            raise RuntimeError(f'Header {header_text!r} not found for {self._widget!r}')

        header_view_obj = self._widget.find_child({'type': 'QHeaderView', 'visible': 1})
        header_view_bounds = header_view_obj.bounds()
        cell_bounds = self.row(0)._cell(header_index).bounds()
        return ScreenRectangle(
            cell_bounds.x, header_view_bounds.y,
            cell_bounds.width, header_view_bounds.height,
            )

    def click_header(self, header_text: str):
        # TODO: maybe transform this into sort by.
        self._hid.mouse_left_click(self.header_bounds(header_text).center())
        time.sleep(1)

    def column_values(self, column_name: str) -> List[str]:
        return [row.cell(column_name).get_display_text() for row in self.all_rows()]

    def all_rows(self) -> Sequence['_TableRow']:
        row_count = self._get_model().call_method('rowCount')
        return [self.row(i) for i in range(row_count)]

    def row(self, i):
        return _TableRow(self._hid, self._widget, i, self._columns)

    def get_row_index_by_values(
            self,
            **column_kwargs,  # column name / value pair as in self._columns
            ):
        _logger.debug('Looking for row with values: %s', column_kwargs)
        all_rows = self.all_rows()
        if not all_rows:
            raise RuntimeError("No accessible rows in table")
        [columns, values] = zip(*column_kwargs.items())
        for [row_i, row] in enumerate(all_rows):
            if [*row.values(columns)] == [*values]:
                return row_i
        return None

    def find_row(
            self,
            **column_kwargs,  # column name / value pair as in self._columns
            ):
        _logger.debug('Looking for row with values: %s', column_kwargs)
        if not self.all_rows():
            raise RuntimeError("No accessible rows in table")
        for row in self.all_rows():
            [columns, values] = zip(*column_kwargs.items())
            if [*row.values(columns)] == [*values]:
                return row
        raise RowNotFound(f"Cannot find row {column_kwargs}")

    def uncheck_all_rows(self):
        for row in self.all_rows():
            cell = row.cell('selection_box')
            if cell.is_checked():
                row.leftmost_cell().click()

    def select_all_by_hotkey(self):
        self._hid.keyboard_hotkeys('Ctrl', 'A')

    def wait_for_inaccessible(self, timeout: float = 3):
        self._widget.wait_for_inaccessible(timeout)

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)

    def is_accessible(self):
        return self._widget.is_accessible_timeout(3)

    @property
    def json_model(self):
        return json.loads(str(self._widget.wait_for_object().call_method('jsonContents')))

    def is_accessible_timeout(self, timeout_sec: float) -> bool:
        return self._widget.is_accessible_timeout(timeout_sec)


class RowNotFound(Exception):
    pass


class _TableRow:

    def __init__(self, hid: HID, widget: Widget, i: int, columns: Sequence[str]):
        self._columns = columns
        self._widget = widget
        self._hid = hid
        self._i = i

    def is_selected(self) -> bool:
        # We treat a row as selected if its 0 cell is selected.
        return self.leftmost_cell().is_selected()

    def leftmost_cell(self) -> '_TableCell':
        return self._cell(0)

    def cell(self, column_name) -> '_TableCell':
        col_i = self._columns.index(column_name)
        return self._cell(col_i)

    def data(self) -> Mapping[str, str]:
        return dict(zip(self._columns, self.values(self._columns)))

    def values(self, columns: Sequence[str]) -> Sequence[str]:
        r = []
        for col_name in columns:
            col_i = self._columns.index(col_name)
            cell = self._cell(col_i)
            value = cell.get_display_text()
            r.append(value)
        return r

    def images(self) -> Sequence[ImageCapture]:
        r = {}
        for [col_i, col_name] in enumerate(self._columns):
            cell = self._cell(col_i)
            image = cell.image_capture()
            r[col_name] = image
        return r

    def _cell(self, col_i) -> '_TableCell':
        return _TableCell.find(self._hid, self._widget, self._i, col_i)


class _TableCell(ClickableObject):

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def get_display_text(self):
        return str(self._widget.wait_for_object().call_method('data', 0))

    def get_text(self):
        return str(self._widget.wait_property('text', timeout=0))

    def is_checked(self):
        return str(self._widget.wait_property('checkState', timeout=0)) == 'checked'

    def is_selected(self):
        return bool(self._widget.wait_property('selected', timeout=0))

    def click(self):
        self._hid.mouse_left_click_on_object(self._widget)

    def right_click(self):
        self._hid.mouse_right_click_on_object(self._widget)

    def ctrl_click(self):
        self._hid.mouse_left_click_on_object(self._widget, modifier=ControlModifier)

    def shift_click(self):
        self._hid.mouse_left_click_on_object(self._widget, modifier=ShiftModifier)

    def double_click(self):
        self._hid.mouse_double_click_on_object(self._widget)

    def context_menu(self, item_name):
        self.right_click()
        menu = QMenu(self._widget._api, self._hid)
        item = menu._widget.find_child({'text': item_name}, timeout=5)
        self._hid.mouse_left_click_on_object(item)

    def image_capture(self):
        return self._widget.image_capture()

    def tooltip(self):
        return str(self._widget.wait_property('toolTip', timeout=0))

    @classmethod
    def find(cls, hid: HID, table_widget: Widget, row_i: int, col_i: int):
        cell = table_widget.find_child(
            properties={
                'type': 'QModelIndex',
                'row': row_i,
                'column': col_i,
                },
            timeout=1,
            )
        return cls(cell, hid)


class QTreeView:

    def __init__(self, widget: Widget):
        self._widget = widget

    def item_names(self):
        r = []
        children = self._widget.find_children({'type': 'QModelIndex'}, timeout=0)
        # TODO: Consider filtering by column=0
        for child in children:
            text = child.wait_property('text', timeout=0)
            if text:
                r.append(text)
        return r

    def get_item_coordinate(self, name: str) -> ScreenPoint:
        item = self._widget.find_child({'text': name})
        return item.bounds().top_left().right(65).down(15)

    def is_accessible_timeout(self, timeout: float):
        # Timeout in seconds.
        try:
            self._widget.wait_for_object(timeout)
            return True
        except testkit.ObjectNotFound:
            return False

    def wait_for_accessible(self, timeout: float):
        self._widget.wait_for_accessible(timeout)


class QSlider:

    def __init__(self, widget: Widget, min_value=0, max_value=100):
        self._widget = widget
        self._min_value = min_value
        self._max_value = max_value

    def _get_min(self) -> int:
        return self._min_value

    def _get_max(self) -> int:
        return self._max_value

    def get_value(self):
        return self._widget.wait_property('value')

    def set(self, value: int):
        _logger.info('%r: set position to %s', self.__class__.__name__, value)
        if not self._get_min() <= value <= self._get_max():
            raise ValueError()
        self._widget.wait_for_object().call_method('setValue', value)


class QSpinBox(QLineEdit):

    def __init__(self, hid: HID, widget: Widget):
        super().__init__(hid, widget)

    def spin_up(self):
        self._widget.wait_for_object().call_method('stepUp')

    def spin_down(self):
        self._widget.wait_for_object().call_method('stepDown')

    def set(self, current_value: int, target_value: int):
        _logger.debug('Set %s value to %s', self.__class__.__name__, target_value)
        delta = target_value - current_value

        def spin():
            self.spin_down() if delta < 0 else self.spin_up()

        for _ in range(abs(delta)):
            spin()
            time.sleep(.5)

    def wait_for_accessible(self, timeout: float = 3):
        self._widget.wait_for_accessible(timeout)

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class QList:

    def __init__(self, widget: Widget):
        self._widget = widget

    def _get_items(self) -> Sequence['Widget']:
        return self._widget.find_children({'type': 'QModelIndex'})

    def get_values(self) -> List[str]:
        return [item.get_text() for item in self._get_items()]


class QQuickImage(ClickableObject):

    def __init__(self, obj: Widget):
        self._widget = obj

    def get_painted_size(self):
        return (
            int(self._widget.wait_property('paintedWidth')),
            int(self._widget.wait_property('paintedHeight')),
            )

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class TabWidget:

    def __init__(self, widget: Widget):
        self._widget = widget

    def find_tab(self, tab_name: str) -> Widget:
        return self._widget.find_child({
            'type': 'TabItem',
            'text': tab_name,
            'enabled': True,
            'visible': True,
            })

    def has_tab(self, tab_name: str):
        return bool(self._widget.find_children({'text': tab_name}))

    def get_current_index(self):
        return self._widget.wait_property('currentIndex')


class QmlTabWidget(TabWidget):

    def find_tab(self, tab_name: str) -> Widget:
        return self._widget.find_child({
            'id': 'tabText',
            'text': tab_name,
            'enabled': True,
            'visible': True,
            })


class HtmlTextItem:

    def __init__(self, widget: Widget):
        self._widget = widget

    def html(self):
        return str(self._widget.wait_property('html'))


class TimelineZoomButton:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def click(self):
        self._hid.mouse_press(self._widget.center())
        time.sleep(.5)
        self._hid.mouse_release(self._widget.center())


class TextField(ClickableObject):

    def __init__(self, hid: HID, widget: Widget):
        self._widget = widget
        self._hid = hid

    def type_text(self, text: str):
        if text == '':
            # Sending an empty string does not clear the text in the field, as might be expected.
            raise TextForTextFieldIsEmpty()
        self._hid.mouse_left_click_on_object(self._widget)
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.write_text(text)

    def clear(self):
        self._hid.mouse_left_click_on_object(self._widget)
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.keyboard_hotkeys('Backspace')

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def is_enabled(self) -> bool:
        return self._widget.is_enabled()

    def get_text(self) -> str:
        return self._widget.get_text()


class _SwitchIconState(Enum):
    DISABLED = 0
    ENABLED = 2


class SwitchIcon:

    def __init__(self, obj: Widget, hid: HID):
        self._obj = obj
        self._hid = hid

    def is_checked(self):
        state = self._obj.wait_property('checkState')
        if state == _SwitchIconState.ENABLED.value:
            return True
        elif state == _SwitchIconState.DISABLED.value:
            return False
        else:
            raise RuntimeError("Unknown switch icon state")

    def set(self, state: bool):
        if self.is_checked() != state:
            self._hid.mouse_left_click_on_object(self._obj)


class QmlListView:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def get_options_with_names(self):
        options = {}
        options_objects = self._widget.find_children({
            'visible': True,
            'type': 'QQuickText',
            })
        for option in options_objects:
            title = option.get_text().replace("&nbsp;", " ")
            options[title] = option
        return options

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class QmlTable:

    def __init__(self, widget: Widget, hid: HID, columns: Sequence[str]):
        self._widget = widget
        self._hid = hid
        self._columns = columns

    def find_row(
            self,
            **column_kwargs,  # Column name / value pair as in self._columns
            ):
        _logger.debug('Looking for row with values: %s', column_kwargs)
        if not self.all_rows():
            raise RuntimeError("No accessible rows in table")
        for row in self.all_rows():
            [columns, values] = zip(*column_kwargs.items())
            if [*row.values(columns)] == [*values]:
                return row
        raise RowNotFound(f"Cannot find row {column_kwargs}")

    def all_rows(self) -> Sequence['_QmlTableRow']:
        row_count = self._widget.wait_property('rows')
        return [self.row(i) for i in range(row_count)]

    def row(self, i: int) -> '_QmlTableRow':
        return _QmlTableRow(self._hid, self._widget, i, self._columns)


class _QmlTableRow:

    def __init__(self, hid: HID, widget: Widget, i: int, columns: Sequence[str]):
        self._columns = columns
        self._widget = widget
        self._hid = hid
        self._i = i

    def cell(self, column_name) -> '_QmlTableCell':
        col_i = self._columns.index(column_name)
        return self._cell(col_i)

    def values(self, columns: Sequence[str]) -> Sequence[str]:
        r = []
        for col_name in columns:
            col_i = self._columns.index(col_name)
            cell = self._cell(col_i)
            value = cell.get_text()
            r.append(value)
        return r

    def _cell(self, col_i) -> '_QmlTableCell':
        return _QmlTableCell.find(self._hid, self._widget, self._i, col_i)


class _QmlTableCell(ClickableObject):

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def get_text(self):
        return str(self._widget.wait_property('text', timeout=0))

    def image_capture(self):
        return self._widget.image_capture()

    @classmethod
    def find(cls, hid: HID, table_widget: Widget, row_i: int, col_i: int):
        cell = table_widget.find_child(
            properties={
                'id': 'basicTableCellDelegate',
                'row': row_i,
                'column': col_i,
                },
            timeout=1,
            )
        return cls(cell, hid)


class TextForTextFieldIsEmpty(Exception):
    ...
