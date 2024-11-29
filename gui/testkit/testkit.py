# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import re
import time
from pathlib import Path
from pprint import pformat
from typing import Any
from typing import Mapping
from typing import Sequence
from urllib.error import URLError
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from gui.desktop_ui.screen import ScreenRectangle
from gui.testkit._exceptions import ObjectAttributeNotFound
from gui.testkit._exceptions import TestKitConnectionError

_JS_CODE_FILEPATH = Path(__file__).with_name('testkit.js')


class TestKit:
    """Wrapper for TestKit C++ class, see testkit.h for API details."""

    def __init__(self, host: str, port: int):
        self.url = f'http://{host}:{port}'
        self._repr = f'{self.__class__.__name__}({host}, {port})'

    def __repr__(self):
        return self._repr

    def connect(self, timeout: float = 20):
        start = time.monotonic()
        js_code_data = _JS_CODE_FILEPATH.read_text()
        while True:
            try:
                response = self.execute('testkit')
                if 'error' in response:
                    raise _TestKitInitializationError(response)
                _testkit_metric('connect', '', 'success', time.monotonic() - start)
                self.execute(js_code_data)
                return
            except TestKitConnectionError as e:
                exception = e
                _logger.info('TestKit server is not running. The client has not started yet')
            except _TestKitInitializationError as e:
                exception = e
                _logger.info('TestKit not ready yet: %s', e)
            if time.monotonic() - start > timeout:
                _testkit_metric('connect', '', 'fail', time.monotonic() - start)
                raise exception
            time.sleep(1)

    def reset_cache(self):
        self.execute('__testkit_cache = {}; testkit.onEvent(null); gc();')

    def execute(self, source):
        data = self._command({'command': 'execute', 'source': source})
        return data

    def execute_function(self, name: str, *args):
        def _dump_arguments(obj):
            if isinstance(obj, (_Object, _Variant)):
                return obj.serialize()
            elif isinstance(obj, dict):
                attrs = [
                    f'{json.dumps(attr)}: {_dump_arguments(value)}'
                    for attr, value in obj.items()]
                return '{' + ','.join(attrs) + '}'
            return json.dumps(obj, default=serialize_internal)

        args_dumped = ','.join(_dump_arguments(a) for a in args)
        started_at = time.monotonic()
        try:
            result = self.execute(f'{name}({args_dumped})')
        except TestKitConnectionError:
            _testkit_metric(name, args_dumped, 'fail', time.monotonic() - started_at)
            raise TestKitConnectionError('The Client unexpectedly terminated or froze')
        _testkit_metric(name, args_dumped, 'success', time.monotonic() - started_at)
        return result

    def screenshot(self):
        req = Request(f'{self.url}/screenshot.png')
        resp = urlopen(req)
        return resp.read()

    def find_object(self, params):
        prepared_params = _prepare_parameters_with_regex_patterns(params)
        response = self.execute_function('find_object', prepared_params)
        return self.deserialize(response.get('result'))

    def find_objects(self, params):
        prepared_params = _prepare_parameters_with_regex_patterns(params)
        return self.deserialize(self.execute_function('find_objects', prepared_params))

    def bounds(self, obj: '_Object') -> ScreenRectangle:
        response = self.execute_function('testkit.bounds', obj)
        return ScreenRectangle(**response['result'])

    def deserialize(self, response):
        if response is None:
            return None

        r_type = response.get('type')
        r_result = response.get('result')
        r_object_id = response.get('id')
        if response.get('error'):
            # Sometimes, an error message can be very long (e.g., in the 'Found several elements'
            # case). Such lengthy messages are almost useless, so let's truncate them to 2000
            # characters.
            error_message = pformat(r_result)
            raise RuntimeError(f'{response["errorString"]}: {error_message[:2000]}')
        if response.get('metatype') == 'QVariant':
            return _Variant(r_result)
        elif response.get('metatype') == 'QUrl':
            return r_result
        elif r_type in ('object', 'qobject'):
            return _Object(self, r_object_id)
        elif r_type == 'array':
            return [self.deserialize(item) for item in r_result]
        return r_result  # raw value

    def get_time_frame_points(self) -> Sequence[int]:
        data = self._command({"command": "getFrameTimePoints"})
        if int(data.get('error', 0)) != 0:
            raise TestKitConnectionError(
                f"The command getFrameTimePoints failed: [{data['error']}] {data['errorString']}")
        return data["framePoints"]

    def _command(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _logger.debug("Request: %s", payload)
        data = urlencode(payload, quote_via=quote).encode()
        request = Request(self.url, data=data)
        started_at = time.monotonic()
        while True:
            try:
                response = urlopen(request, timeout=10)
            except (URLError, ConnectionResetError, TimeoutError) as exc:
                if time.monotonic() - started_at > 20:
                    raise TestKitConnectionError(f"Connection error: {exc}")
                time.sleep(1)
                _logger.warning("TestKit connection error, retrying...")
            else:
                break
        _logger.debug("Response: [%r] %s", response.status, response.reason)
        response_body_raw = response.read()
        response_body_stripped = response_body_raw.decode(errors='backslashreplace').strip()
        _logger.debug("Response body: %s", response_body_stripped)
        data = json.loads(response_body_raw)
        return data

    def get_locator(self, obj: '_Object') -> Mapping[str, Any]:
        """Get prepared locator of the object.

        This method is for debugging and researching purposes only.
        We have a limited list of properties for searching objects.
        Available properties based on the TestKit source file:
        nx/open/vms/client/nx_vms_client_desktop/src/nx/vms/client/desktop/testkit/utils_match.cpp

        Example of usage in scratch:
            from testkit.testkit import TestKit

            api = TestKit(host='127.0.0.1', port=port)
            dialog_locator = {
                'container': {"type": "nx::vms::client::desktop::MainWindow"},
                "type": "QnSystemAdministrationDialog",
                }
            objects = api.find_objects(dialog_locator)
            for obj in objects:
                print(api.get_locator(obj))
        """
        available_properties = [
            'visible',
            'enabled',
            'selected',
            'text',
            'name',
            'objectName',
            'title',
            'id',
            'unnamed',
            'toolTip',
            'labelText',
            'type',
            'window',
            'source',
            'column',
            'row',
            'x',
            'y',
            'z',
            'checkState',
            ]
        full_result = self.execute_function('testkit.dump', obj).get('result')
        if full_result is None:
            return {}
        filtered_result = {}
        for available_property in available_properties:
            if available_property in full_result:
                filtered_result[available_property] = full_result[available_property]
        return filtered_result


def serialize_internal(obj):
    """JSON serializer for objects not serializable by default json code."""
    return obj.__dict__


def _prepare_parameters_with_regex_patterns(parameters: dict[str, Any]) -> dict[str, Any]:
    """Prepare Parameters with Regular Expression Patterns.

    Replace any regular expression objects in the parameters dictionary
    with a string representation of their patterns.

    >>> import re
    >>> locator = {'text': re.compile('pattern1'), 'title': re.compile('pattern2')}
    >>> _prepare_parameters_with_regex_patterns(locator)
    {'text': 're:pattern1', 'title': 're:pattern2'}
    >>> locator = {'text': 'example'}
    >>> _prepare_parameters_with_regex_patterns(locator)
    {'text': 'example'}
    >>> locator = {'name': re.compile('Button|QButton')}
    >>> _prepare_parameters_with_regex_patterns(locator)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    RuntimeError: Regular expressions are only allowed for the following properties:...
    """
    regex_supported_properties = ['text', 'title', 'tooltip', 'source', 'labelText']
    for key, val in parameters.items():
        if isinstance(val, re.Pattern):
            if key in regex_supported_properties:
                parameters[key] = f're:{val.pattern}'
            else:
                raise RuntimeError(
                    f"Regular expressions are only allowed for the following properties: "
                    f"{regex_supported_properties}. Received property {key!r} "
                    f"with pattern {val.pattern!r}",
                    )
    return parameters


# Fake variant type
class _Variant:

    def __init__(self, value=None):
        self._value = value

    def __getitem__(self, name):
        return self._value.get(name)

    def __getattr__(self, name):
        return getattr(self._value, name)

    def __int__(self):
        try:
            return int(self._value)
        except (ValueError, TypeError):
            return 0

    def __str__(self):
        return str(self._value)

    def serialize(self) -> str:
        return json.dumps(self._value, default=serialize_internal)


class _Object:

    def __init__(self, testkit: TestKit, object_id: str):
        self._testkit = testkit
        self._id = object_id  # Use it to access object properties and methods

    def serialize(self) -> str:
        return f'__testkit_cache[{json.dumps(self._id)}]'

    @property
    def id(self) -> str:
        return self._id

    def call_method(self, name: str, *args):
        response = self._testkit.execute_function('call_object_method', self.id, name, args or None)
        if response.get('type') is None:
            raise ObjectAttributeNotFound(f'No method {name!r} in {self}')
        return self._testkit.deserialize(response.get('result'))

    def get_attr(self, name: str):
        response = self._testkit.execute_function('get_object_property', self.id, name)
        if response.get('type') is None:
            raise ObjectAttributeNotFound(f'No property {name!r} in {self}')
        return self._testkit.deserialize(response.get('result'))

    def set_attr(self, name, value):
        self._testkit.execute_function('set_object_property', self.id, name, value)

    def __repr__(self):
        return self.id


class _TestKitInitializationError(Exception):
    pass


def _testkit_metric(command: str, args: str, state: str, execution_time_sec: float):
    metric = {
        'testkit': {
            'command': command,
            'args': args,
            'state': state,
            'execution_time_sec': execution_time_sec,
            },
        }
    _logger.info("Testkit metric: %r", metric)


_logger = logging.getLogger(__name__)
