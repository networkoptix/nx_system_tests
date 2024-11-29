# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# See: https://www.w3.org/TR/webdriver2
import base64
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Mapping
from typing import NoReturn
from typing import Optional
from typing import Sequence
from urllib.parse import quote
from xml.sax.saxutils import escape

from browser._bounding_rectangle import BoundingRectangle


class Browser:

    def __init__(self, webdriver_session: 'WebDriverSession'):
        self._webdriver_session = webdriver_session

    def open(self, url: str):
        result = self._webdriver_session.post("/url", {"url": url})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")

    def get_current_url(self) -> str:
        try:
            return self._webdriver_session.get_json("/url")
        except WebDriverError as err:
            if err.error == 'no such execution context':
                raise PageNotLoaded()
            raise

    def get_title(self) -> str:
        return self._webdriver_session.get_json("/title")

    @lru_cache()
    def request_mouse(self) -> '_MousePointer':
        return _MousePointer("mouse", self._webdriver_session)

    @lru_cache()
    def request_keyboard(self) -> 'Keyboard':
        return Keyboard("keyboard", self._webdriver_session)

    def wait_element(self, selector: 'ElementSelector', timeout: float) -> 'WebDriverElement':
        return selector.wait_in(_VirtualRootElement(self._webdriver_session), timeout)

    def refresh(self):
        result = self._webdriver_session.post("/refresh", {})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")

    def get_current_tab(self) -> '_TabHandle':
        result = self._webdriver_session.get_json("/window")
        return _TabHandle(self._webdriver_session, result)

    def get_tabs(self) -> Sequence['_TabHandle']:
        result = self._webdriver_session.get_json("/window/handles")
        return [_TabHandle(self._webdriver_session, tab_handle) for tab_handle in result]

    def open_in_tab(self, url: str) -> '_TabHandle':
        result = self._webdriver_session.post("/window/new", {})
        tab = _TabHandle(self._webdriver_session, result['handle'])
        tab.switch_to()
        result = self._webdriver_session.post("/url", {"url": url})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")
        return tab

    def scroll_to_bottom(self):
        _execute_synchronous_javascript(
            self._webdriver_session,
            """window.scrollTo(0, document.body.scrollHeight);""")

    def get_logs(self):
        types = self._webdriver_session.get_json('/se/log/types')
        result = {}
        for t in types:
            result[t] = self._webdriver_session.post('/se/log', {'type': t})
        return result

    def close(self):
        self._webdriver_session.delete("", {})


def _execute_synchronous_javascript(
        webdriver_session: 'WebDriverSession',
        script: str,
        arguments: Sequence[Any] = (),
        ) -> Any:
    script_arguments = {"script": script, "args": arguments}
    return webdriver_session.post('/execute/sync', script_arguments)


class Keyboard:

    def __init__(self, name: str, webdriver_session: 'WebDriverSession'):
        self._name = name
        self._webdriver_session = webdriver_session

    def send_keys(self, keys: str, modifiers: str = ''):
        actions = []
        for key in keys:
            actions.extend([_KeyPress(key), _Pause(50), _KeyRelease(key), _Pause(50)])
        for modifier in reversed(modifiers):
            actions.insert(0, _Pause(50))
            actions.insert(0, _KeyPress(modifier))
            actions.append(_Pause(50))
            actions.append(_KeyRelease(modifier))
        self._perform(actions)

    def _perform(self, actions: Sequence['_Action']):
        actions_chain = [action.get_webdriver_structure() for action in actions]
        keyboard_actions = {"type": "key", "id": self._name, "actions": actions_chain}
        result = self._webdriver_session.post("/actions", {"actions": [keyboard_actions]})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")


class ElementClickIntercepted(Exception):
    pass


class ElementNotFound(Exception):
    pass


class ElementNotInteractable(Exception):
    pass


class StaleElementReference(Exception):
    pass


class PageNotLoaded(Exception):
    pass


class PropertyNotFound(Exception):
    pass


class AttributeNotFound(Exception):
    pass


class MultipleElementsFound(Exception):
    pass


class WebDriverError(Exception):

    def __init__(self, error: str, message: str):
        self.error = error
        self.message = message

    def __repr__(self):
        return f'<WebDriverError: [{self.error}] {self.message}>'


class ElementSelector:

    def __init__(self, location_strategy: str, selector: str):
        self._location_strategy = location_strategy
        self._selector = selector

    def wait_in(self, element: '_DOMElement', timeout: float) -> 'WebDriverElement':
        search_expression = {"using": self._location_strategy, "value": self._selector}
        timeout_at = time.monotonic() + timeout
        while True:
            if post_result := element.http_post("/elements", search_expression):
                elements = [element.get_child(element_struct) for element_struct in post_result]
                if len(elements) == 1:
                    return elements[0]
                raise MultipleElementsFound(f"Multiple elements are identified by {self}: {elements}")
            if time.monotonic() > timeout_at:
                raise ElementNotFound(f"Can't find element identified by {self}")
            time.sleep(0.5)

    def find_in(self, element: '_DOMElement') -> 'WebDriverElement':
        search_expression = {"using": self._location_strategy, "value": self._selector}
        if post_result := element.http_post("/elements", search_expression):
            elements = [element.get_child(element_struct) for element_struct in post_result]
            if len(elements) == 1:
                return elements[0]
            raise MultipleElementsFound(f"Multiple elements are identified by {self}: {elements}")
        raise ElementNotFound(f"Can't find element identified by {self}")

    def find_all_in(self, element: '_DOMElement') -> Sequence['WebDriverElement']:
        search_expression = {"using": self._location_strategy, "value": self._selector}
        post_result = element.http_post("/elements", search_expression)
        return [element.get_child(element_struct) for element_struct in post_result]

    def __repr__(self):
        return f'{self.__class__.__name__}({self._location_strategy!r}, {self._selector!r})'


class ByXPATH(ElementSelector):

    @classmethod
    def quoted(cls, printf_template: str, *args: str):
        return cls(printf_template % tuple(_quoted_text(arg) for arg in args))

    def __init__(self, selector: str):
        super().__init__('xpath', selector)

    def find_in(self, element: '_DOMElement') -> 'WebDriverElement':
        if not isinstance(element, _VirtualRootElement) and self._selector.startswith("/"):
            raise ValueError(
                "Only relative XPATH location paths are allowed in non-root nodes. "
                f"{self._selector} is an absolute location path.")
        return super().find_in(element)

    def find_all_in(self, element: '_DOMElement') -> Sequence['WebDriverElement']:
        if not isinstance(element, _VirtualRootElement) and self._selector.startswith("/"):
            raise ValueError(
                "Only relative XPATH location paths are allowed in non-root nodes. "
                f"{self._selector} is an absolute location path.")
        return super().find_all_in(element)


class ByText(ElementSelector):

    def __init__(self, text: str):
        quoted_text_selector = _quoted_text(text)
        super().__init__('xpath', f"//*[text()[contains(.,{quoted_text_selector})]]")


def _quoted_text(text: str) -> str:
    # The XPath expressions are encoded in accordance with XML 1.0 rules
    # See: https://www.w3.org/TR/1999/REC-xpath-19991116/
    return "'" + escape(text, entities={"'": "&apos;", '"': "&quot;"}) + "'"


class ByCSS(ElementSelector):
    """Element CSS selector.

    See: https://www.w3schools.com/cssref/css_selectors.php
    """

    def __init__(self, value: str):
        super().__init__('css selector', value)


def get_visible_text(element: 'WebDriverElement') -> str:
    return element.http_get("/text")


class _DOMElement(metaclass=ABCMeta):

    def __init__(self, webdriver_session: 'WebDriverSession'):
        self._webdriver_session = webdriver_session

    def get_child(self, element_id: Mapping[str, str]) -> 'WebDriverElement':
        return WebDriverElement(self._webdriver_session, _ElementID.extract_from(element_id))

    @abstractmethod
    def http_post(self, path: str, params: Mapping[str, Any]) -> Optional[Any]:
        pass


class _VirtualRootElement(_DOMElement):

    def http_post(self, path, params):
        full_path = f"/{path.lstrip('/')}"
        try:
            result = self._webdriver_session.post(full_path, params)
        except WebDriverError as err:
            if err.error == 'stale element reference':
                raise StaleElementReference(
                    "A stale element ID is received. Probably the page has been reloaded. "
                    f"{self} should be re-created")
            if err.error == 'no such element' and err.message == 'No node with given id found':
                raise StaleElementReference(
                    "Received 'Element not found' error while a stale element ID is received. "
                    "See: https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440")
            raise
        return result


class WebDriverElement(_DOMElement):

    def __init__(self, webdriver_session: 'WebDriverSession', id_: '_ElementID'):
        super().__init__(webdriver_session)
        self._id = id_

    def http_get(self, path: str) -> Optional[Any]:
        full_path = f"/element/{self._id.value()}/{path.lstrip('/')}"
        try:
            result = self._webdriver_session.get_json(full_path)
        except WebDriverError as err:
            if err.error == 'stale element reference':
                raise StaleElementReference(
                    "A stale element ID is received. Probably the page has been reloaded. "
                    f"{self} should be re-created")
            if err.error == 'no such element' and err.message == 'No node with given id found':
                raise StaleElementReference(
                    "Received 'Element not found' error while a stale element ID is received. "
                    "See: https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440")
            raise
        return result

    def http_post(self, path, params):
        full_path = f"/element/{self._id.value()}/{path.lstrip('/')}"
        try:
            result = self._webdriver_session.post(full_path, params)
        except WebDriverError as err:
            if err.error == 'stale element reference':
                raise StaleElementReference(
                    "A stale element ID is received. Probably the page has been reloaded. "
                    f"{self} should be re-created")
            if err.error == 'no such element' and err.message == 'No node with given id found':
                raise StaleElementReference(
                    "Received 'Element not found' error while a stale element ID is received. "
                    "See: https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440")
            if err.error == 'element not interactable':
                raise ElementNotInteractable(f"{self} is not interactable")
            if err.error == 'element click intercepted':
                raise ElementClickIntercepted(f"{self} is obscured by another element")
            raise
        return result

    def invoke(self):
        result = self.http_post("/click", {})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")

    def get_dom_string_property(self, property_name: str) -> str:
        quoted_property_name = quote(property_name)
        result = self.http_get(f"/property/{quoted_property_name}")
        if result is None:
            raise RuntimeError(f"{self} does not contain property {property_name}")
        if not isinstance(result, str):
            raise RuntimeError(f"{self} property {property_name} is not str: {result}")
        return result

    def get_dom_bool_property(self, property_name: str) -> bool:
        quoted_property_name = quote(property_name)
        result = self.http_get(f"/property/{quoted_property_name}")
        if result is None:
            raise RuntimeError(f"{self} does not contain property {property_name}")
        if not isinstance(result, bool):
            raise RuntimeError(f"{self} property {property_name} is not bool: {result}")
        return result

    def execute_javascript_function(self, script: str):
        """
        Executes JavaScript function with the web element itself as 1-st argument.

        Use 'arguments[0]' in JS script to address the element itself.
        """
        # WebDriver expects only a JavaScript function body and creates an anonymous function
        # with this body. So the passed function must be wrapped and called explicitly.
        # See: https://www.w3.org/TR/webdriver/#execute-script
        # See: https://github.com/jlipps/simple-wd-spec?tab=readme-ov-file#execute-script
        script = f'return ({script})(arguments);'
        script_arguments = [self._id.serialize()]
        return _execute_synchronous_javascript(self._webdriver_session, script, script_arguments)

    def get_css_value(self, value_name: str) -> str:
        quoted_value_name = quote(value_name)
        result = self.http_get(f"/css/{quoted_value_name}")
        if result is None:
            raise RuntimeError(f"{self} does not contain CSS value {quoted_value_name}")
        return result

    def get_attribute(self, name: str) -> str:
        quoted_attribute_name = quote(name)
        result = self.http_get(f"/attribute/{quoted_attribute_name}")
        if result is None:
            raise AttributeNotFound(f"{self} does not contain attribute {name}")
        if not isinstance(result, str):
            raise RuntimeError(f"{self} attribute {name} is not str: {result}")
        return result

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._id.value()}>'


class _ElementID:

    # See: https://www.w3.org/TR/webdriver2/#dfn-web-element-identifier
    _key = "element-6066-11e4-a52e-4f735466cecf"

    @classmethod
    def extract_from(cls, structure: Mapping[str, str]):
        id_value = structure.get(cls._key)
        if id_value is None:
            raise RuntimeError(
                f"Can't parse {structure} as Web Driver ID structure. "
                f"{cls._key} key is absent")
        return cls(id_value)

    def __init__(self, _id: str):
        self._id = _id

    def serialize(self) -> Mapping[str, str]:
        return {self._key: self._id}

    def value(self) -> str:
        return self._id


class VisibleElement:

    def __init__(self, webdriver_element: WebDriverElement):
        self._webdriver_element = webdriver_element

    def get_text(self) -> str:
        return get_visible_text(self._webdriver_element)

    def invoke(self):
        self._webdriver_element.invoke()

    def is_focused(self) -> bool:
        script = Path(__file__).with_name('is_focused.js').read_text()
        result = self._webdriver_element.execute_javascript_function(script)
        if not isinstance(result, bool):
            raise RuntimeError(f"Unexpected value {result} received instead of a boolean one")
        return result

    def get_bounding_rect(self) -> BoundingRectangle:
        raw_rect = self._webdriver_element.http_get("/rect")
        return BoundingRectangle(
            raw_rect['x'], raw_rect['y'], raw_rect['width'], raw_rect['height'])

    def get_image_bytes(self) -> 'bytes':
        result = self._webdriver_element.http_get('/screenshot')
        if result is None:
            raise RuntimeError(f"Can't get screenshot of {self}")
        decoded = base64.b64decode(result)
        return decoded

    def get_cursor_style(self) -> str:
        return self._webdriver_element.get_css_value("cursor")

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self._webdriver_element}>"


class _TabHandle:

    def __init__(self, webdriver_session: 'WebDriverSession', id_: str):
        self._webdriver_session = webdriver_session
        self._id = id_

    def switch_to(self):
        self._webdriver_session.post("/window", {"handle": self._id})

    def close(self):
        current_tab_id = self._webdriver_session.get_json("/window")
        self._webdriver_session.post("/window", {"handle": self._id})
        self._webdriver_session.delete("/window", {})
        if current_tab_id != self._id:
            self._webdriver_session.post("/window", {"handle": current_tab_id})

    def __repr__(self):
        return f"<Tab: {self._id}>"


class WebDriverSession(metaclass=ABCMeta):

    @abstractmethod
    def post(self, path: str, json_data: Mapping[str, Any]) -> Optional[Any]:
        pass

    @abstractmethod
    def get_json(self, path: str) -> Optional[Any]:
        pass

    @abstractmethod
    def delete(self, path: str, json_data: Mapping[str, Any]):
        pass


class _Action:

    @abstractmethod
    def get_webdriver_structure(self) -> Mapping[str, Any]:
        pass


class _MoveInViewPort(_Action):

    @classmethod
    def round_subpixel(cls, x: float, y: float):
        # While coordinates are mostly returned in floats, a pointer uses integer coordinates.
        # There might be sub-pixels precision problems but probability of facing them is negligible.
        return cls(round(x), round(y))

    def __init__(self, x: int, y: int):
        self._x = x
        self._y = y

    def get_webdriver_structure(self):
        return {
            "type": "pointerMove",
            "duration": 250,
            "x": self._x,
            "y": self._y,
            "origin": "viewport",
            }


class _Pause(_Action):

    def __init__(self, duration_tick: int):
        self._duration_tick = duration_tick

    def get_webdriver_structure(self):
        return {"type": "pause", "duration": self._duration_tick}


class _MouseLeftDown(_Action):

    def get_webdriver_structure(self):
        return {"type": "pointerDown", "duration": 0, "button": 0}


class _MouseLeftUp(_Action):

    def get_webdriver_structure(self):
        return {"type": "pointerUp", "duration": 0, "button": 0}


class _MouseRightDown(_Action):

    def get_webdriver_structure(self):
        return {"type": "pointerDown", "duration": 0, "button": 1}


class _MouseRightUp(_Action):

    def get_webdriver_structure(self):
        return {"type": "pointerUp", "duration": 0, "button": 1}


class _MousePointer:

    def __init__(self, name: str, webdriver_session: WebDriverSession):
        self._name = name
        self._webdriver_session = webdriver_session

    def drag_n_drop(
            self,
            source: tuple[float, float],
            destination: tuple[float, float],
            pause_after_action_ms=10,
            ):
        self._perform(
            _MoveInViewPort.round_subpixel(*source),
            _Pause(pause_after_action_ms),
            _MouseLeftDown(),
            _Pause(pause_after_action_ms),
            _MoveInViewPort.round_subpixel(*destination),
            _Pause(pause_after_action_ms),
            _MouseLeftUp(),
            )

    def click(self, coordinates: tuple[float, float]):
        self._perform(
            _MoveInViewPort.round_subpixel(*coordinates),
            _Pause(10),
            _MouseLeftDown(),
            _Pause(10),
            _MouseLeftUp(),
            )

    def hover(self, coordinates: tuple[float, float]):
        move_to_action = _MoveInViewPort.round_subpixel(*coordinates)
        self._perform(move_to_action)

    def _perform(self, *actions: _Action):
        mouse_actions_chain = {
            "type": "pointer",
            "id": self._name,
            "parameters": {"pointerType": "mouse"},
            "actions": [action.get_webdriver_structure() for action in actions],
            }
        result = self._webdriver_session.post("/actions", {"actions": [mouse_actions_chain]})
        if result is not None:
            raise RuntimeError(f"Unexpected value: {result}")


class _KeyPress(_Action):

    def __init__(self, key: str):
        if len(key) != 1:
            raise RuntimeError(f"Key must be exactly one character, {key!r} received")
        self._key = key

    def get_webdriver_structure(self):
        return {"type": "keyDown", "value": self._key}


class _KeyRelease(_Action):

    def __init__(self, key: str):
        if len(key) != 1:
            raise RuntimeError(f"Key must be exactly one character, {key!r} received")
        self._key = key

    def get_webdriver_structure(self):
        return {"type": "keyUp", "value": self._key}


def raise_webdriver_error(data: Mapping[str, Any]) -> NoReturn:
    raise WebDriverError(data["error"], data["message"])


class Keys:
    """
    All values are Unicode codepoints.

    See: https://www.w3.org/TR/webdriver2/#keyboard-actions
    See: https://codepoints.net/private_use_area
    """

    NULL = "\ue000"
    CANCEL = "\ue001"
    HELP = "\ue002"
    BACKSPACE = "\ue003"
    TAB = "\ue004"
    CLEAR = "\ue005"
    RETURN = "\ue006"
    ENTER = "\ue007"
    SHIFT = "\ue008"
    CONTROL = "\ue009"
    ALT = "\ue00a"
    PAUSE = "\ue00b"
    ESCAPE = "\ue00c"
    SPACE = "\ue00d"
    PAGE_UP = "\ue00e"
    PAGE_DOWN = "\ue00f"
    END = "\ue010"
    HOME = "\ue011"
    ARROW_LEFT = "\ue012"
    ARROW_UP = "\ue013"
    ARROW_RIGHT = "\ue014"
    ARROW_DOWN = "\ue015"
    INSERT = "\ue016"
    DELETE = "\ue017"
    SEMICOLON = "\ue018"
    EQUALS = "\ue019"
    NUMPAD0 = "\ue01a"
    NUMPAD1 = "\ue01b"
    NUMPAD2 = "\ue01c"
    NUMPAD3 = "\ue01d"
    NUMPAD4 = "\ue01e"
    NUMPAD5 = "\ue01f"
    NUMPAD6 = "\ue020"
    NUMPAD7 = "\ue021"
    NUMPAD8 = "\ue022"
    NUMPAD9 = "\ue023"
    MULTIPLY = "\ue024"
    ADD = "\ue025"
    SEPARATOR = "\ue026"
    SUBTRACT = "\ue027"
    DECIMAL = "\ue028"
    DIVIDE = "\ue029"
    F1 = "\ue031"
    F2 = "\ue032"
    F3 = "\ue033"
    F4 = "\ue034"
    F5 = "\ue035"
    F6 = "\ue036"
    F7 = "\ue037"
    F8 = "\ue038"
    F9 = "\ue039"
    F10 = "\ue03a"
    F11 = "\ue03b"
    F12 = "\ue03c"
    META = "\ue03d"
    COMMAND = "\ue03d"
    ZENKAKU_HANKAKU = "\ue040"


# See: https://www.w3schools.com/cssref/pr_class_cursor.php
class CursorStyle:
    NOT_ALLOWED = 'not-allowed'


_logger = logging.getLogger(__name__.split('.')[-1])
