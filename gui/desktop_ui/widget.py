# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Optional
from typing import Sequence
from typing import Union

from gui import testkit
from gui.desktop_ui.media_capturing import Screenshot
from gui.desktop_ui.media_capturing import VideoCapture
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.screen import ScreenRectangle
from gui.testkit.hid import ClickableObject
from gui.testkit.testkit import TestKit
from gui.testkit.testkit import _Object

_logger = logging.getLogger(__name__)

_default_wait_timeout = 20  # seconds


class Widget(ClickableObject):

    def __init__(self, api: TestKit, locator_or_obj: Union[dict, _Object]):
        self._api: TestKit = api
        self._obj: Optional[_Object] = None
        self._locator: Optional[dict] = None
        if isinstance(locator_or_obj, dict):
            self._locator: dict = locator_or_obj
        else:
            self._obj = locator_or_obj

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._locator or self._obj!r}>'

    def _get_obj(self) -> _Object:
        if self._obj is not None:
            return self._obj
        obj = self._api.find_object(self._locator)
        if obj is None:
            raise testkit.ObjectNotFound(f'Object {self._locator!r} is not found!')
        return obj

    def wait_for_object(self, timeout: float = _default_wait_timeout) -> _Object:
        _logger.debug(
            'Waiting for object %s. Timeout: %s second(s)',
            self._locator or self._obj, timeout)
        start = time.monotonic()
        while True:
            try:
                if not self.wait_property('visible', 0):
                    raise testkit.ObjectAttributeValueError(
                        f'Object {self._locator or self._obj!r} is not visible')
                if not self.wait_property('enabled', 0):
                    raise testkit.ObjectAttributeValueError(
                        f'Object {self._locator or self._obj!r} is not enabled')
                break
            except (
                    testkit.ObjectAttributeValueError,
                    testkit.ObjectAttributeNotFound,
                    ) as e:
                if time.monotonic() - start > timeout:
                    raise testkit.ObjectNotFound(e)
            time.sleep(.1)
        return self._get_obj()

    def get_text(self) -> str:
        return str(self.wait_property('text'))

    def is_accessible(self) -> bool:
        return self.is_accessible_timeout(3)

    def is_accessible_timeout(self, timeout: float) -> bool:
        # Timeout in seconds.
        try:
            self.wait_for_object(timeout)
            return True
        except testkit.ObjectNotFound:
            return False

    def is_enabled(self) -> bool:
        try:
            return self.wait_property('enabled') is True
        except testkit.ObjectAttributeNotFound:
            return False

    def is_visible(self) -> bool:
        try:
            return self.wait_property('visible') is True
        except testkit.ObjectAttributeNotFound:
            return False

    def wait_for_accessible(self, timeout: float = 3):
        _logger.debug(
            'Waiting for object %s accessible. Timeout %s second(s)',
            self._locator or self._obj, timeout)
        start_time = time.monotonic()
        while True:
            if self.is_accessible_timeout(0.1):
                return
            if time.monotonic() - start_time > timeout:
                raise WidgetIsNotAccessible(f"Object {self._locator or self._obj!r} is not accessible")
            time.sleep(.1)

    def wait_for_inaccessible(self, timeout: float = 3):
        _logger.debug(
            'Waiting for object %s inaccessible. Timeout %s second(s)',
            self._locator or self._obj, timeout)
        start_time = time.monotonic()
        while True:
            if not self.is_accessible_timeout(0.1):
                return
            if time.monotonic() - start_time > timeout:
                raise WidgetIsAccessible(f"Object {self._locator or self._obj!r} is accessible")
            time.sleep(.1)

    def bounds(self) -> ScreenRectangle:
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
                if time.monotonic() - start > _default_wait_timeout:
                    raise testkit.ObjectNotFound(e)
            time.sleep(.1)
        return self._api.bounds(self._get_obj())

    def center(self) -> ScreenPoint:
        return self.bounds().center()

    def image_capture(self) -> Screenshot:
        buffer = self._api.screenshot()
        bounds = self.bounds()
        return Screenshot(buffer, bounds)

    def video(self, duration_seconds: float = 5) -> VideoCapture:
        frames = []
        self.wait_for_object()
        start = time.monotonic()
        while time.monotonic() - start < duration_seconds:
            capture = self.image_capture()
            frames.append(capture)
        return VideoCapture(frames)

    def find_children(
            self,
            properties: dict,
            timeout: float = _default_wait_timeout,
            ) -> Sequence['Widget']:
        _logger.debug(
            'Looking for children of %s with properties: %s',
            self._locator or self._obj, properties)
        children = self._api.find_objects({
            'container': self.wait_for_object(timeout),
            **properties,
            })
        return [Widget(self._api, child) for child in children]

    def find_child(
            self,
            properties: dict,
            timeout: float = _default_wait_timeout,
            ) -> 'Widget':
        _logger.debug(
            'Looking for child of %s with properties: %s',
            self._locator or self._obj, properties)
        child = Widget(self._api, {
            'container': self.wait_for_object(timeout),
            **properties,
            })
        return child

    def wait_property(self, property_name: str, timeout: float = _default_wait_timeout):
        start_time = time.monotonic()
        while True:
            try:
                return self._get_obj().get_attr(property_name)
            except (testkit.ObjectNotFound, testkit.ObjectAttributeNotFound) as e:
                if time.monotonic() - start_time > timeout:
                    raise testkit.ObjectAttributeNotFound(e)
            time.sleep(0.1)

    def set_attribute_value(self, attribute_name: str, value):
        _logger.debug('%r: Set "%s" value to "%s"', self, attribute_name, value)
        obj = self._get_obj()
        obj.set_attr(attribute_name, value)


class WidgetIsNotAccessible(Exception):
    pass


class WidgetIsAccessible(Exception):
    pass
