# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import platform
import urllib
from abc import ABCMeta
from abc import abstractmethod
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urlparse

if platform.machine() == 'armv7l':  # RPI
    import RPi.GPIO
import requests

_logger = logging.getLogger(__name__)


class ChannelMode(Enum):
    OUT = 0
    IN = 1


class PinMode(Enum):
    OUT = "out"
    IN = "in"


class NotFound(Exception):
    pass


class ChannelNotFound(NotFound):
    pass


class PinNotFound(NotFound):
    pass


class DeviceNotFound(NotFound):
    pass


class ChannelLabelsRead(metaclass=ABCMeta):

    @abstractmethod
    def get_connected_channel(self, device_name, pin_name):
        pass


class ChannelLabelsWrite(metaclass=ABCMeta):

    @abstractmethod
    def assign_pin_to_channel(self, device_name, pin_name, pin_mode, channel):
        pass

    @abstractmethod
    def unassign_pin_from_channel(self, device_name, pin_name):
        pass

    _PinAttrs = namedtuple('_PinAttrs', ['device_name', 'pin_name', 'pin_mode', 'channel'])

    @abstractmethod
    def list_assignments(self):
        pass


class JsonFileLabels(ChannelLabelsRead, ChannelLabelsWrite):

    def __init__(self, path_to_json):
        self.path_to_json = path_to_json
        if not self.path_to_json.exists() or self.path_to_json.stat().st_size == 0:
            with open(self.path_to_json, 'w') as f:
                f.write('{}')
        with open(self.path_to_json, 'r') as f:
            self.device_to_connected_pins = json.loads(f.read())

    def __repr__(self):
        return str(self.device_to_connected_pins)

    def _overwrite_json_content(self):
        with open(self.path_to_json, 'w') as f:
            json.dump(self.device_to_connected_pins, f)

    def get_connected_channel(self, device_name, pin_name):
        try:
            connected_pins = self.device_to_connected_pins[device_name]
        except KeyError:
            raise DeviceNotFound(f"No device {device_name} found in Device-Pins config")
        try:
            return connected_pins[pin_name]['channel']
        except KeyError:
            raise PinNotFound(
                f"{device_name}: no pin_name {pin_name} found in Device-Pins config")

    def assign_pin_to_channel(self, device_name, pin_name, pin_mode, channel):
        connected_pins = self.device_to_connected_pins.setdefault(device_name, {})
        connected_pins[pin_name] = {'channel': channel, 'pin_mode': pin_mode.value}
        self._overwrite_json_content()

    def unassign_pin_from_channel(self, device_name, pin_name):
        try:
            connected_pins = self.device_to_connected_pins[device_name]
        except KeyError:
            raise DeviceNotFound(f"{device_name}: No such device")
        try:
            channel_and_pin_mode = connected_pins.pop(pin_name)
        except KeyError:
            raise PinNotFound(f"{device_name}: No pin with name {pin_name}")
        self._overwrite_json_content()
        # Returning channel because we need to pass it to RewiringManager.disconnect_device_pin():
        # channel is passed to IoRewiring.disable_channel() there
        return channel_and_pin_mode['channel']

    def list_assignments(self):
        result = []
        for device_name, connected_pins in self.device_to_connected_pins.items():
            for pin_name, channel_and_pin_mode in connected_pins.items():
                result.append(
                    self._PinAttrs(
                        device_name,
                        pin_name,
                        PinMode(channel_and_pin_mode['pin_mode']),
                        channel_and_pin_mode['channel'],
                        ))
        return result


class InMemoryDictLabels(ChannelLabelsRead, ChannelLabelsWrite):

    def __init__(self, initial_dict):
        self._validate_dict(initial_dict)
        self.device_to_connected_pins = initial_dict

    def __repr__(self):
        return str(self.device_to_connected_pins)

    @staticmethod
    def _validate_dict(d):
        for device_name, connected_pins in d.items():
            if not isinstance(connected_pins, dict):
                raise TypeError(
                    f"{device_name}: connected_pins has to be a dict instance in {device_name}: "
                    f"connected_pins pair, {type(connected_pins)} instance provided")
            for pin_name, pin_attrs in connected_pins.items():
                if not isinstance(pin_attrs, dict):
                    raise TypeError(
                        f"f{device_name}: {pin_name}: pin_attrs has to be a dict instance in "
                        f"{pin_name}: pin_attrs pair, {type(pin_attrs)} provided")
                if not pin_attrs:
                    continue
                supported_attrs_names = ('channel', 'pin_mode')
                if not all(key in supported_attrs_names for key in pin_attrs.keys()):
                    raise RuntimeError(
                        f"{device_name}: {pin_name}: unexpected attribute names provided. Expected"
                        f" attributes names are {supported_attrs_names}")

    def get_connected_channel(self, device_name, pin_name):
        try:
            connected_pins = self.device_to_connected_pins[device_name]
        except KeyError:
            raise DeviceNotFound(f"No device {device_name} found in Device-Pins config")
        try:
            return connected_pins[pin_name]['channel']
        except KeyError:
            raise PinNotFound(
                f"{device_name}: no pin_name {pin_name} found in Device-Pins config")

    def assign_pin_to_channel(self, device_name, pin_name, pin_mode, channel):
        connected_pins = self.device_to_connected_pins.setdefault(device_name, {})
        connected_pins[pin_name] = {'channel': channel, 'pin_mode': pin_mode.value}

    def unassign_pin_from_channel(self, device_name, pin_name):
        try:
            connected_pins = self.device_to_connected_pins[device_name]
        except KeyError:
            raise DeviceNotFound(f"{device_name}: No such device")
        try:
            channel_and_pin_mode = connected_pins.pop(pin_name)
        except KeyError:
            raise PinNotFound(f"{device_name}: no pin with name {pin_name}")
        return channel_and_pin_mode['channel']

    def list_assignments(self):
        result = []
        for device_name, connected_pins in self.device_to_connected_pins.items():
            for pin_name, channel_and_pin_mode in connected_pins.items():
                result.append(
                    self._PinAttrs(
                        device_name,
                        pin_name,
                        PinMode(channel_and_pin_mode['pin_mode']),
                        channel_and_pin_mode['channel'],
                        ))
        return result


class IoSwitch(metaclass=ABCMeta):

    @abstractmethod
    def activate_out(self, channel):
        pass

    @abstractmethod
    def deactivate_out(self, channel):
        pass

    @abstractmethod
    def read_channel(self, channel):
        pass


class IoRewiring(metaclass=ABCMeta):

    @abstractmethod
    def set_channel_to_input(self, channel):
        pass

    @abstractmethod
    def set_channel_to_output(self, channel):
        pass

    @abstractmethod
    def disable_channel(self, channel):
        pass

    @abstractmethod
    def list_channels(self):
        pass


class RpiGpioDevice(IoSwitch, IoRewiring):

    def __init__(self):
        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setwarnings(False)

    @staticmethod
    def _get_channel_mode(channel):
        return ChannelMode(RPi.GPIO.gpio_function(channel))

    def activate_out(self, channel):
        RPi.GPIO.output(int(channel), RPi.GPIO.HIGH)

    def deactivate_out(self, channel):
        RPi.GPIO.output(int(channel), RPi.GPIO.LOW)

    def read_channel(self, channel):
        mode = self._get_channel_mode(channel)
        state = RPi.GPIO.input(int(channel))
        if mode == ChannelMode.IN:
            # We are pulling the INs up -> statuses are inverted for them
            return state == 0
        return state == 1

    def set_channel_to_input(self, channel):
        RPi.GPIO.setup(int(channel), RPi.GPIO.IN, pull_up_down=RPi.GPIO.PUD_UP)

    def set_channel_to_output(self, channel):
        RPi.GPIO.setup(int(channel), RPi.GPIO.OUT)

    def disable_channel(self, channel):
        RPi.GPIO.cleanup(int(channel))

    def list_channels(self):
        result = []
        for channel in range(2, 27):  # Channels 2-26 are configurable GPIO pins
            mode = self._get_channel_mode(channel)
            result.append((channel, mode))
        return result


class VirtualGpioDevice(IoSwitch, IoRewiring):

    @dataclass
    class _ChannelAttrs:
        mode: ChannelMode
        enabled: bool
        is_set: bool

    def __init__(self, channels=range(2, 27)):
        self._channel_to_attrs = {
            channel: self._ChannelAttrs(ChannelMode.IN, False, False)
            for channel in channels}

    def _get_channel_attrs(self, channel):
        try:
            channel_attrs = self._channel_to_attrs[channel]
        except KeyError:
            raise ChannelNotFound(f"Channel {channel} was not found")
        return channel_attrs

    def _switch_out_state(self, channel, enabled: bool):
        channel_attrs = self._get_channel_attrs(channel)
        if channel_attrs.mode != ChannelMode.OUT:
            raise RuntimeError("Channel mode is not set to OUT")
        if not channel_attrs.is_set:
            raise RuntimeError("Channel has to be setup first")
        channel_attrs.enabled = enabled

    def activate_out(self, channel):
        self._switch_out_state(channel, True)

    def deactivate_out(self, channel):
        self._switch_out_state(channel, False)

    def read_channel(self, channel):
        channel_attrs = self._get_channel_attrs(channel)
        if not channel_attrs.is_set:
            raise RuntimeError("Channel has to be setup first")
        return channel_attrs.enabled

    def set_channel_to_input(self, channel):
        channel_attrs = self._get_channel_attrs(channel)
        channel_attrs.mode = ChannelMode.IN
        channel_attrs.is_set = True

    def set_channel_to_output(self, channel):
        channel_attrs = self._get_channel_attrs(channel)
        channel_attrs.mode = ChannelMode.OUT
        channel_attrs.is_set = True

    def disable_channel(self, channel):
        channel_attrs = self._get_channel_attrs(channel)
        channel_attrs.mode = ChannelMode.IN
        channel_attrs.is_set = False
        # Seems that RPi.GPIO does not reset the "enabled" state, so we keep it here as well

    def list_channels(self):
        return [(channel, attrs.mode) for channel, attrs in self._channel_to_attrs.items()]

    def set_input_channel_state(self, channel, enable):
        # Used in functional tests, imitates behavior of a connected device output pin
        channel_attrs = self._get_channel_attrs(channel)
        mode = channel_attrs.mode
        if mode != ChannelMode.IN:
            raise RuntimeError(
                f"Channel {channel}: expected mode: IN, current mode: {ChannelMode(mode).name}")
        channel_attrs.enabled = enable


class RewiringManager(metaclass=ABCMeta):

    @abstractmethod
    def connect_device_input_pin(self, device_name, pin_name, channel):
        pass

    @abstractmethod
    def connect_device_output_pin(self, device_name, pin_name, channel):
        pass

    @abstractmethod
    def disconnect_device_pin(self, device_name, pin_name):
        pass

    @abstractmethod
    def list_connections(self):
        pass

    @abstractmethod
    def fix_channel_mode(self, channel):
        pass


class IoManager(metaclass=ABCMeta):

    @abstractmethod
    def activate_device_input_pin(self, device_name, pin_name):
        pass

    @abstractmethod
    def deactivate_device_input_pin(self, device_name, pin_name):
        pass

    @abstractmethod
    def device_pin_is_enabled(self, device_name, pin_name):
        pass


class LocalRewiringManager(RewiringManager):

    def __init__(
            self,
            channel_labels_updater: ChannelLabelsWrite,
            io_rewiring: IoRewiring,
            ):
        self.channel_labels_updater = channel_labels_updater
        self.io_rewiring = io_rewiring
        for pin_attrs in self.channel_labels_updater.list_assignments():
            if pin_attrs.pin_mode == PinMode.OUT:
                self.io_rewiring.set_channel_to_input(pin_attrs.channel)
            else:
                self.io_rewiring.set_channel_to_output(pin_attrs.channel)

    def connect_device_input_pin(self, device_name, pin_name, channel):
        _logger.info(
            "%s: connecting pin %s to channel %s as IN pin", device_name, pin_name, channel)
        self.io_rewiring.set_channel_to_output(channel)
        self.channel_labels_updater.assign_pin_to_channel(
            device_name, pin_name, PinMode.IN, channel)

    def connect_device_output_pin(self, device_name, pin_name, channel):
        _logger.info(
            "%s: connecting pin %s to channel %s as OUT pin", device_name, pin_name, channel)
        self.io_rewiring.set_channel_to_input(channel)
        self.channel_labels_updater.assign_pin_to_channel(
            device_name, pin_name, PinMode.OUT, channel)

    def disconnect_device_pin(self, device_name, pin_name):
        _logger.info("%s: disconnecting pin %s", device_name, pin_name)
        channel = self.channel_labels_updater.unassign_pin_from_channel(device_name, pin_name)
        if channel is not None:
            self.io_rewiring.disable_channel(channel)

    def list_connections(self):
        result = []
        _ChannelAttrs = namedtuple(
            '_ChannelAttrs', ['device_name', 'pin_name', 'pin_mode', 'channel', 'channel_mode'])
        for channel, channel_mode in self.io_rewiring.list_channels():
            for pin_attrs in self.channel_labels_updater.list_assignments():
                if pin_attrs.channel == channel:
                    result.append(
                        _ChannelAttrs(
                            pin_attrs.device_name,
                            pin_attrs.pin_name,
                            pin_attrs.pin_mode,
                            channel,
                            channel_mode))
                    break
            else:
                result.append(
                    _ChannelAttrs(None, None, None, channel, channel_mode))
        return result

    def fix_channel_mode(self, channel):
        for ch_attrs in self.list_connections():
            if channel == ch_attrs.channel:
                break
        else:
            raise ChannelNotFound(f"Channel {channel} not found, can't fix channel mode")
        if ch_attrs.channel_mode == ChannelMode.OUT:
            self.io_rewiring.set_channel_to_input(channel)
        else:
            self.io_rewiring.set_channel_to_output(channel)


class HTTPClient:

    def __init__(self, http_server_addr='0.0.0.0:8080'):
        if not isinstance(http_server_addr, str):
            raise TypeError("HttpClient: http_server_addr is expected to be a string")
        self.server_url = urllib.parse.urlparse(f'http://{http_server_addr}')

    def prepare_url(self, path):
        return self.server_url._replace(path=path).geturl()

    def _check_connectivity(self):
        try:
            requests.get(self.prepare_url(''))
        except requests.ConnectionError:
            raise _GPIOHttpAppInaccessible()


class _GPIOHttpAppInaccessible(Exception):
    pass


class RemoteRewiringManager(RewiringManager, HTTPClient):

    def is_accessible(self):
        try:
            self._check_connectivity()
        except _GPIOHttpAppInaccessible:
            _logger.warning("No connection to GPIO HttpApp on %s", self.server_url.geturl())
            return False
        _logger.info("GPIO HttpApp on %s is accessible", self.server_url.geturl())
        return True

    def connect_device_input_pin(self, device_name, pin_name, channel):
        data = json.dumps({'device_name': device_name, 'pin_name': pin_name, 'channel': channel})
        result = requests.post(self.prepare_url('/rewiring/connect_device_input_pin'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"connect_device_input_pin returned {result.status_code} code. Error is "
                f"{result.text}")

    def connect_device_output_pin(self, device_name, pin_name, channel):
        data = json.dumps({'device_name': device_name, 'pin_name': pin_name, 'channel': channel})
        result = requests.post(self.prepare_url('/rewiring/connect_device_output_pin'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"connect_device_output_pin returned {result.status_code} code. Error is "
                f"{result.text}")

    def disconnect_device_pin(self, device_name, pin_name):
        data = json.dumps({'device_name': device_name, 'pin_name': pin_name})
        result = requests.post(self.prepare_url('/rewiring/disconnect_device_pin'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"disconnect_device_pin returned {result.status_code} code. Error is {result.text}")

    def fix_channel_mode(self, channel):
        data = json.dumps({'channel': channel})
        result = requests.post(self.prepare_url('/rewiring/fix_channel_mode'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"fix_channel_mode returned {result.status_code} code. Error is "
                f"{result.text}")

    def list_connections(self):
        result = requests.get(self.prepare_url('/rewiring/list_connections'))
        if result.status_code != 200:
            raise RuntimeError(
                f"list_connections returned {result.status_code} code. Error is {result.text}")


class LocalIoManager(IoManager):

    def __init__(self, channel_labels_reader: ChannelLabelsRead, io_switch: IoSwitch):
        self.channel_labels_reader = channel_labels_reader
        self.io_switch = io_switch

    def activate_device_input_pin(self, device_name, pin_name):
        _logger.info("%s: activating input %s", device_name, pin_name)
        channel = self.channel_labels_reader.get_connected_channel(
            device_name, pin_name)
        self.io_switch.activate_out(channel)

    def deactivate_device_input_pin(self, device_name, pin_name):
        _logger.info("%s: deactivating input %s", device_name, pin_name)
        channel = self.channel_labels_reader.get_connected_channel(
            device_name, pin_name)
        self.io_switch.deactivate_out(channel)

    def device_pin_is_enabled(self, device_name, pin_name):
        _logger.info("%s: getting pin %s state", device_name, pin_name)
        channel = self.channel_labels_reader.get_connected_channel(
            device_name, pin_name)
        enabled = self.io_switch.read_channel(channel)
        _logger.info("%s: pin %s state is %s", device_name, pin_name, enabled)
        return enabled


class RemoteIoManager(IoManager, HTTPClient):

    def activate_device_input_pin(self, device_name, pin_name):
        data = json.dumps({'device_name': device_name, 'pin_name': pin_name})
        result = requests.post(self.prepare_url('io/activate_device_input_pin'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"activate_device_input_pin returned {result.status_code} code. Error is "
                f"{result.text}")

    def deactivate_device_input_pin(self, device_name, pin_name):
        data = json.dumps({'device_name': device_name, 'pin_name': pin_name})
        result = requests.post(self.prepare_url('io/deactivate_device_input_pin'), data)
        if result.status_code != 200:
            raise RuntimeError(
                f"deactivate_device_input_pin returned {result.status_code} code. Error is "
                f"{result.text}")

    def device_pin_is_enabled(self, device_name, pin_name):
        query = urlencode({'device_name': device_name, 'pin_name': pin_name})
        result = requests.get(self.prepare_url(f'io/device_pin_is_enabled?{query}'))
        if result.status_code != 200:
            raise RuntimeError(
                f"device_pin_is_enabled returned {result.status_code} code; error: {result.text}")
        state = json.loads(result.text)['state']
        if state == 'Enabled':
            return True
        return False


class _HTTPHandler(BaseHTTPRequestHandler):
    server: 'HTTPApp'

    @staticmethod
    def _get_supported_api():
        return {
            'rewiring': {
                'GET': {
                    'list_connections': (),
                    },
                'POST': {
                    'connect_device_input_pin': ('device_name', 'pin_name', 'channel'),
                    'connect_device_output_pin': ('device_name', 'pin_name', 'channel'),
                    'disconnect_device_pin': ('device_name', 'pin_name'),
                    'fix_channel_mode': ('channel', ),
                    },
                },
            'io': {
                'GET': {
                    'device_pin_is_enabled': ('device_name', 'pin_name'),
                    },
                'POST': {
                    'activate_device_input_pin': ('device_name', 'pin_name'),
                    'deactivate_device_input_pin': ('device_name', 'pin_name'),
                    },
                },
            }

    def _parse_path(self, method, parsed_url_path):
        result = {'error': None, 'manager': None, 'action': None, 'query_names': ()}
        path = Path(parsed_url_path.path)
        supported_api = self._get_supported_api()
        try:
            _, manager_key, action_key = path.parts
        except ValueError:
            result['error'] = {
                'code': 400, 'explain': "Expected path form is /<manager>/<action>"}
            return result
        result['manager'] = manager_key
        result['action'] = action_key
        try:
            result['query_names'] = supported_api[manager_key][method][action_key]
        except KeyError:
            result['error'] = {'code': 404, 'explain': "Unexpected path part(s) provided"}
        return result

    @staticmethod
    def _query_error(expected_query_names, actual_query: dict):
        if not all(name in actual_query.keys() for name in expected_query_names):
            return {
                'code': 403,
                'message': "Unexpected query/data keys",
                'explain': f"Expected keys are: {expected_query_names}",
                }
        return {}

    def _send_index_html(self):
        self.send_response(200)
        bytes = Path(__file__).with_name('index.html').read_bytes()
        self.send_header('Content-length', str(len(bytes)))
        self.end_headers()
        self.wfile.write(bytes)

    def _prepare_list_connections_result(self):
        result_list = []
        for ch_attrs in self.server.rewiring_manager.list_connections():
            res = {
                'channel_mode': 'in' if ch_attrs.channel_mode == ChannelMode.IN else 'out',
                'channel': ch_attrs.channel,
                }
            if all(value is not None for value in (
                    ch_attrs.device_name, ch_attrs.pin_name, ch_attrs.pin_mode)):
                res = {
                    'device_name': ch_attrs.device_name,
                    'pin_name': ch_attrs.pin_name,
                    'pin_mode': ch_attrs.pin_mode.value,
                    **res,
                    }
            result_list.append(res)
        return json.dumps(result_list)

    def _prepare_device_pin_is_enabled_result(self, query):
        # Get rid of lists in query values: we expect only single values in the method
        kwargs = {key: value for key, [value] in query.items()}
        result = self.server.io_manager.device_pin_is_enabled(**kwargs)
        if result:
            res_str = 'Enabled'
        else:
            res_str = 'Disabled'
        return json.dumps({'state': res_str})

    def _send_result(self, json_result):
        encoded = json_result.encode()
        content_length = len(encoded)
        self.send_response(200)
        self.send_header('Content-length', str(content_length))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == '/':
            self._send_index_html()
            return
        parsed_url_path = urlparse(self.path)
        parsed_path = self._parse_path('GET', parsed_url_path)
        if parsed_path['error'] is not None:
            self.send_error(**parsed_path['error'])
            return
        actual_query = parse_qs(parsed_url_path.query)
        query_error = self._query_error(
            parsed_path['query_names'], actual_query)
        if query_error:
            self.send_error(**query_error)
            return
        try:
            if parsed_path['action'] == 'list_connections':
                json_result = self._prepare_list_connections_result()
            elif parsed_path['action'] == 'device_pin_is_enabled':
                json_result = self._prepare_device_pin_is_enabled_result(actual_query)
            else:
                self.send_error(400, f"Unsupported action: {parsed_path['action']}")
                return
        except Exception as e:
            self.send_error(500, message=f"{type(e).__name__} occurred", explain=str(e))
            return
        self._send_result(json_result)
        return

    def _load_post_data(self):
        content_length = int(self.headers.get('content-length', 0))
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode())

    def _post_is_ok(self):
        self.send_response(200)
        self.send_header('Content-length', '0')
        self.end_headers()

    def do_POST(self):
        data = self._load_post_data()
        parsed_path = self._parse_path('POST', urlparse(self.path))
        if parsed_path['error'] is not None:
            self.send_error(**parsed_path['error'])
            return
        data_error = self._query_error(parsed_path['query_names'], data)
        if data_error:
            self.send_error(**data_error)
            return
        try:
            if parsed_path['action'] == 'connect_device_input_pin':
                self.server.rewiring_manager.connect_device_input_pin(**data)
            if parsed_path['action'] == 'connect_device_output_pin':
                self.server.rewiring_manager.connect_device_output_pin(**data)
            if parsed_path['action'] == 'disconnect_device_pin':
                self.server.rewiring_manager.disconnect_device_pin(**data)
            if parsed_path['action'] == 'activate_device_input_pin':
                self.server.io_manager.activate_device_input_pin(**data)
            if parsed_path['action'] == 'deactivate_device_input_pin':
                self.server.io_manager.deactivate_device_input_pin(**data)
            if parsed_path['action'] == 'fix_channel_mode':
                self.server.rewiring_manager.fix_channel_mode(**data)
        except Exception as e:
            self.send_error(500, message=f"{type(e).__name__} occurred", explain=str(e))
            return
        self._post_is_ok()
        return

    def log_message(self, format, *args):
        _logger.debug(format, *args)


class HTTPApp(TCPServer):
    """Server for GPIO.

    Do not inherit HTTPServer, because it spends 1 sec on socket.getfqdn().
    """

    def __init__(
            self,
            rewiring_manager: RewiringManager,
            io_manager: IoManager,
            server_address=('0.0.0.0', 8080),
            ):
        super(HTTPApp, self).__init__(server_address, _HTTPHandler)
        self.rewiring_manager = rewiring_manager
        self.io_manager = io_manager


def main():
    labels_manager = JsonFileLabels(Path(__file__).with_name('labels.json'))
    io_device = RpiGpioDevice()
    rewiring_manager = LocalRewiringManager(labels_manager, io_device)
    io_manager = LocalIoManager(labels_manager, io_device)
    http_server = HTTPApp(rewiring_manager, io_manager)
    http_server.serve_forever()


if __name__ == '__main__':
    main()
