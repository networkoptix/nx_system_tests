# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import string
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Mapping

from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.screen import ScreenRectangle
from gui.testkit._exceptions import MouseModifierValueError
from gui.testkit._exceptions import TestKitConnectionError
from gui.testkit._exceptions import TypedTextValueError
from gui.testkit.testkit import TestKit

_logger = logging.getLogger(__name__)

NoModifier = 0x00000000  # No modifier key is pressed.
ShiftModifier = 0x02000000  # A Shift key on the keyboard is pressed.
ControlModifier = 0x04000000  # A Ctrl key on the keyboard is pressed.
AltModifier = 0x08000000  # An Alt key on the keyboard is pressed.

_modifiers = [
    NoModifier,
    ShiftModifier,
    ControlModifier,
    AltModifier,
    ]
_modifiers_hex = [f'0x{m:08x}' for m in _modifiers]


def _validate_mouse_modifier(value: int):
    if value in _modifiers:
        return
    if not isinstance(value, int):
        raise TypeError(f"Modifier {value!r} is not int")
    raise MouseModifierValueError(
        f"Modifier 0x{value:08x} not in supported {_modifiers_hex}")


def validate_typed_text(text: str):
    if isinstance(text, str):
        unsupported = [c for c in text if c not in string.printable]
        if unsupported:
            raise ValueError(f"Cannot type these symbols: {unsupported!r}")
        return
    raise TypedTextValueError(
        f"Cannot type {text.__class__.__qualname__}: {text!r}")


class ClickableObject(metaclass=ABCMeta):

    @abstractmethod
    def bounds(self) -> ScreenRectangle:
        pass


class HID:

    def __init__(self, api: TestKit):
        self._api = api

    def _send_keyboard_event(self, keys: str, action: str):
        _logger.info('%s: %s %s', self, action.capitalize(), keys)
        self._api.execute_function('testkit.keys', None, keys, action)

    def _send_mouse_event(self, params: Mapping[str, str]):
        self._api.execute_function('testkit.mouse', None, params)

    def _wait_gui_thread_to_done(self):
        # The drag-and-drop implementation in TestKit is based on internal sleeps
        # between mouse moves. The OS implementation of sleep does not guarantee
        # that this sleep will be of a fixed duration. This ONLY means that the
        # sleep duration will be no less than the requested value.
        # Additionally, we need to consider the time taken by the OS to resume
        # threads after a sleep, which can vary each time.
        # Here we request a status of drag-n-drop through a safe manner.
        # See: https://networkoptix.atlassian.net/browse/FT-2251
        start = time.monotonic()
        timeout = 20
        while True:
            time.sleep(1)
            try:
                response = self._api.execute_function('testkit.guiThreadStatus')
                if 'is not a function' in response.get('errorString', ''):
                    _logger.debug('%s: Use constant sleep for old version of VMS', self)
                    time.sleep(3)
                    break

                status = response['result']['status']
            except (KeyError, TestKitConnectionError):
                _logger.debug('%s: Failed to get information about GUI Thread status', self)
            else:
                if not status:
                    _logger.debug(
                        '%s: GUI Thread finished after: %s', self, time.monotonic() - start)
                    break
            _logger.debug(
                '%s: GUI Thread still alive for %s seconds', self, time.monotonic() - start)
        if time.monotonic() - start > timeout:
            raise RuntimeError(f'GUI Thread is not finished within {timeout} seconds timeout')

    @staticmethod
    def _convert_keys(*keys: str) -> str:
        return f"<{'+'.join(keys)}>"

    def write_text(self, text: str):
        validate_typed_text(text)
        self._send_keyboard_event(text, 'type')

    def keyboard_press(self, *keys: str):
        self._send_keyboard_event(self._convert_keys(*keys), 'press')

    def keyboard_release(self, *keys: str):
        self._send_keyboard_event(self._convert_keys(*keys), 'release')

    def keyboard_hotkeys(self, *keys: str):
        self._send_keyboard_event(self._convert_keys(*keys), 'type')

    def mouse_left_click(self, coord: ScreenPoint, modifier: int = NoModifier):
        _logger.debug('%s: Mouse left click: %s', self, coord)
        _validate_mouse_modifier(modifier)
        params = {
            'type': 'click',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            'modifiers': modifier,
            }
        self._send_mouse_event(params)

    def mouse_left_click_on_object(self, obj: ClickableObject, modifier: int = NoModifier):
        _logger.debug('%s: Mouse left click: %s', self, obj)
        self.mouse_left_click(obj.bounds().center(), modifier)

    def mouse_right_click(self, coord: ScreenPoint, modifier: int = NoModifier):
        _logger.debug('%s: Mouse right click: %s', self, coord)
        _validate_mouse_modifier(modifier)
        params = {
            'type': 'click',
            'button': 'right',
            'x': coord.x,
            'y': coord.y,
            'modifiers': modifier,
            }
        self._send_mouse_event(params)

    def mouse_right_click_on_object(self, obj: ClickableObject, modifier: int = NoModifier):
        _logger.debug('%s: Mouse right click: %s', self, obj)
        self.mouse_right_click(obj.bounds().center(), modifier)

    def mouse_double_click_on_object(self, obj: ClickableObject):
        _logger.debug('%s: Mouse doubleclick: %s', self, obj)
        coord = obj.bounds().center()
        params = {
            'type': 'doubleclick',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            }
        self._send_mouse_event(params)

    def mouse_scroll(self, coord: ScreenPoint, scroll_delta: int):
        _logger.debug('%s: Mouse scroll: %s, delta: %s', self, coord, scroll_delta)
        params = {
            'type': 'wheel',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            'scrollDelta': scroll_delta,
            }
        self._send_mouse_event(params)

    def mouse_move(self, coord: ScreenPoint):
        _logger.debug('%s: Mouse move: %s', self, coord)
        params = {
            'type': 'move',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            }
        self._send_mouse_event(params)

    def mouse_press(self, coord: ScreenPoint):
        _logger.debug('%s: Mouse press: %s', self, coord)
        params = {
            'type': 'press',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            }
        self._send_mouse_event(params)

    def mouse_release(self, coord: ScreenPoint):
        _logger.debug('%s: Mouse release: %s', self, coord)
        params = {
            'type': 'release',
            'button': 'left',
            'x': coord.x,
            'y': coord.y,
            }
        self._send_mouse_event(params)

    def mouse_drag_and_drop(
            self,
            obj_coord: ScreenPoint,
            target_coord: ScreenPoint,
            ):
        _logger.debug('%s: Mouse drag and drop from %s to %s', self, obj_coord, target_coord)
        self.mouse_press(obj_coord)
        self.mouse_move(target_coord)
        self.mouse_release(target_coord)

    def mouse_native_drag_and_drop(
            self,
            obj_coord: ScreenPoint,
            target_coord: ScreenPoint,
            steps: int = 300,
            ):
        # Parameter `steps` define the amount of move steps required for drag-n-drop.
        # In some cases, this parameter can be useful, for example, when move distance is too small.
        params = {
            'from': {
                'x': obj_coord.x,
                'y': obj_coord.y,
                },
            'to': {
                'x': target_coord.x,
                'y': target_coord.y,
                },
            'steps': steps,
            }
        _logger.debug('%s: Native mouse drag and drop from %s to %s', self, obj_coord, target_coord)
        self._api.execute_function('testkit.dragAndDrop', None, params)
        self._wait_gui_thread_to_done()
