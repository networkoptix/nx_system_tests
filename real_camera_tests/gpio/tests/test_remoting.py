# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import unittest
from collections import namedtuple
from concurrent.futures.thread import ThreadPoolExecutor

from real_camera_tests.gpio.io_rpi import HTTPApp
from real_camera_tests.gpio.io_rpi import IoManager
from real_camera_tests.gpio.io_rpi import RemoteIoManager
from real_camera_tests.gpio.io_rpi import RemoteRewiringManager
from real_camera_tests.gpio.io_rpi import RewiringManager


class _Logger:

    def __init__(self):
        self.calls = []

    def _decorator(self, method):
        _MethodArgs = namedtuple('_MethodArgs', ['name', 'args', 'kwargs'])

        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            self.calls.append(_MethodArgs(method.__name__, args, kwargs))
            return method(*args, **kwargs)

        return wrapper

    def __getattribute__(self, item):
        value = object.__getattribute__(self, item)
        if callable(value):
            decorator = object.__getattribute__(self, '_decorator')
            return decorator(value)
        return value


class _StubLocalRewiringManager(RewiringManager, _Logger):

    def connect_device_input_pin(self, *args, **kwargs):
        pass

    def connect_device_output_pin(self, *args, **kwargs):
        pass

    def disconnect_device_pin(self, *args, **kwargs):
        pass

    def list_connections(self, *args, **kwargs):
        return ()

    def fix_channel_mode(self, *args, **kwargs):
        pass


class _StubLocalIoManager(IoManager, _Logger):

    def activate_device_input_pin(self, *args, **kwargs):
        pass

    def deactivate_device_input_pin(self, *args, **kwargs):
        pass

    def device_pin_is_enabled(self, *args, **kwargs):
        pass


def _zipped_is_equivalent_to_dict(zipped: zip, normal_dict):
    return all(normal_dict[key] == value for (key, value) in zipped)


def _dicts_are_equivalent(dict_1, dict_2):
    return all(dict_1[key] == dict_2[key] for key in dict_1.keys()) and len(dict_1) == len(dict_2)


def _check_args_and_kwargs(keys, expected, actual):
    if expected['args']:
        zipped = zip(keys, expected['args'])
        assert _zipped_is_equivalent_to_dict(zipped, actual)
    else:
        assert _dicts_are_equivalent(expected['kwargs'], actual)


class TestRemoting(unittest.TestCase):

    def setUp(self):
        self.stub_local_rewiring_manager = _StubLocalRewiringManager()
        self.stub_local_io_manager = _StubLocalIoManager()
        self._http_server = HTTPApp(
            self.stub_local_rewiring_manager,
            self.stub_local_io_manager,
            server_address=('127.0.0.1', 0),
            )
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._http_server.serve_forever)
        addr = '%s:%d' % self._http_server.server_address
        self.remote_rewiring_manager = RemoteRewiringManager(addr)
        self.remote_io_manager = RemoteIoManager(addr)

    def tearDown(self):
        # Close before shutdown. Otherwise it may take 500 ms (poll interval).
        self._http_server.server_close()
        self._http_server.shutdown()
        self._executor.shutdown()

    def test_connect_device_input_pin_args(self):
        self._test_connect_device_input_pin({'args': ('Device_name', 'Input_name', 2), 'kwargs': {}})

    def test_connect_device_input_pin_kwargs(self):
        self._test_connect_device_input_pin({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Input_name', 'channel': 2}})

    def _test_connect_device_input_pin(self, params):
        self.remote_rewiring_manager.connect_device_input_pin(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_rewiring_manager.calls[-1]
        assert 'connect_device_input_pin' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name', 'channel'), params, logged_call.kwargs)
        assert not logged_call.args

    def test_connect_device_output_pin_args(self):
        self._test_connect_device_output_pin({'args': ('Device_name', 'Output_name', 3), 'kwargs': {}})

    def test_connect_device_output_pin_kwargs(self):
        self._test_connect_device_output_pin({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Input_name', 'channel': 3}})

    def _test_connect_device_output_pin(self, params):
        self.remote_rewiring_manager.connect_device_output_pin(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_rewiring_manager.calls[-1]
        assert 'connect_device_output_pin' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name', 'channel'), params, logged_call.kwargs)
        assert not logged_call.args

    def test_disconnect_device_pin_args(self):
        self._test_disconnect_device_pin({'args': ('Device_name', 'Pin_name'), 'kwargs': {}})

    def test_disconnect_device_pin_kwargs(self):
        self._test_disconnect_device_pin({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Pin_name'}})

    def _test_disconnect_device_pin(self, params):
        self.remote_rewiring_manager.disconnect_device_pin(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_rewiring_manager.calls[-1]
        assert 'disconnect_device_pin' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name'), params, logged_call.kwargs)
        assert not logged_call.args

    def test_list_connections(self):
        self.remote_rewiring_manager.list_connections()
        logged_call = self.stub_local_rewiring_manager.calls[-1]
        assert logged_call.name == 'list_connections'
        assert not logged_call.args
        assert not logged_call.kwargs

    def test_fix_channel_mode_args(self):
        self._test_fix_channel_mode({'args': (5,), 'kwargs': {}})

    def test_fix_channel_mode_kwargs(self):
        self._test_fix_channel_mode({'args': (), 'kwargs': {'channel': 5}})

    def _test_fix_channel_mode(self, params):
        self.remote_rewiring_manager.fix_channel_mode(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_rewiring_manager.calls[-1]
        assert 'fix_channel_mode' == logged_call.name
        _check_args_and_kwargs(('channel',), params, logged_call.kwargs)
        assert not logged_call.args

    def test_activate_device_input_pin_args(self):
        self._test_activate_device_input_pin({'args': ('Device_name', 'Input_1'), 'kwargs': {}})

    def test_activate_device_input_pin_kwargs(self):
        self._test_activate_device_input_pin({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Input_1'}})

    def _test_activate_device_input_pin(self, params):
        self.remote_io_manager.activate_device_input_pin(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_io_manager.calls[-1]
        assert 'activate_device_input_pin' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name'), params, logged_call.kwargs)
        assert not logged_call.args

    def test_deactivate_device_input_pin_args(self):
        self._test_deactivate_device_input_pin({'args': ('Device_name', 'Input_1'), 'kwargs': {}})

    def test_deactivate_device_input_pin_kwargs(self):
        self._test_deactivate_device_input_pin({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Input_1'}})

    def _test_deactivate_device_input_pin(self, params):
        self.remote_io_manager.deactivate_device_input_pin(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_io_manager.calls[-1]
        assert 'deactivate_device_input_pin' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name'), params, logged_call.kwargs)
        assert not logged_call.args

    def test_device_pin_is_enabled_args(self):
        self._test_device_pin_is_enabled({'args': ('Device_name', 'Input_1'), 'kwargs': {}})

    def test_device_pin_is_enabled_kwargs(self):
        self._test_device_pin_is_enabled({'args': (), 'kwargs': {'device_name': 'Device_name', 'pin_name': 'Input_1'}})

    def _test_device_pin_is_enabled(self, params):
        self.remote_io_manager.device_pin_is_enabled(*params['args'], **params['kwargs'])
        logged_call = self.stub_local_io_manager.calls[-1]
        assert 'device_pin_is_enabled' == logged_call.name
        _check_args_and_kwargs(('device_name', 'pin_name'), params, logged_call.kwargs)
        assert not logged_call.args
