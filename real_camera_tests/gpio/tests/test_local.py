# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import unittest
from pathlib import Path

from real_camera_tests.gpio.io_rpi import ChannelMode
from real_camera_tests.gpio.io_rpi import ChannelNotFound
from real_camera_tests.gpio.io_rpi import DeviceNotFound
from real_camera_tests.gpio.io_rpi import InMemoryDictLabels
from real_camera_tests.gpio.io_rpi import JsonFileLabels
from real_camera_tests.gpio.io_rpi import LocalIoManager
from real_camera_tests.gpio.io_rpi import LocalRewiringManager
from real_camera_tests.gpio.io_rpi import PinMode
from real_camera_tests.gpio.io_rpi import PinNotFound
from real_camera_tests.gpio.io_rpi import VirtualGpioDevice
from tests.infra import assert_raises

_logger = logging.getLogger(__name__)


class TestLocal(unittest.TestCase):

    def _init_labels(self):
        return {
            "Test_cam": {
                "Output 0": {"channel": 2, "pin_mode": 'out'},
                "Input 0": {"channel": 3, "pin_mode": 'in'},
                },
            }

    def _virtual_gpio_device(self):
        gpio_device = VirtualGpioDevice()
        for pins in self._init_labels().values():
            for pin_data in pins.values():
                if PinMode(pin_data['pin_mode']) == PinMode.OUT:
                    gpio_device.set_channel_to_input(pin_data['channel'])
                else:
                    gpio_device.set_channel_to_output(pin_data['channel'])
        return gpio_device

    def _labels_manager(self, labels_manager_type):
        if labels_manager_type == 'json_file_labels_manager':
            json_path = Path(__file__).with_name('test_labels.json')
            with open(json_path, 'w') as f:
                json.dump(self._init_labels(), f)
            return JsonFileLabels(json_path)
        return InMemoryDictLabels(self._init_labels())

    def test_json_file_labels_manager(self):
        self._test_activate_device_input_pin('json_file_labels_manager')

    def test_in_memory_dict_labels_manager(self):
        self._test_activate_device_input_pin('in_memory_dict_labels_manager')

    def _test_activate_device_input_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Input 0'
        local_io_manager.activate_device_input_pin(device_name, pin_name)
        assert local_io_manager.device_pin_is_enabled(device_name, pin_name)

    def test_deactivate_device_input_pin_json_file_labels_manager(self):
        self._test_deactivate_device_input_pin('json_file_labels_manager')

    def test_deactivate_device_input_pin_in_memory_dict_labels_manager(self):
        self._test_deactivate_device_input_pin('in_memory_dict_labels_manager')

    def _test_deactivate_device_input_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Input 0'
        local_io_manager.deactivate_device_input_pin(device_name, pin_name)
        assert not local_io_manager.device_pin_is_enabled(device_name, pin_name)

    def test_device_output_state_json_file_labels_manager(self):
        self._test_device_output_state('json_file_labels_manager')

    def test_device_output_state_in_memory_dict_labels_manager(self):
        self._test_device_output_state('in_memory_dict_labels_manager')

    def _test_device_output_state(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Output 0'
        channel = 2
        enable = not local_io_manager.device_pin_is_enabled(device_name, pin_name)
        virtual_gpio_device.set_input_channel_state(channel, enable)
        assert local_io_manager.device_pin_is_enabled(device_name, pin_name) == enable

    def test_cannot_change_output_pin_state_json_file_labels_manager(self):
        self._test_cannot_change_output_pin_state('json_file_labels_manager')

    def test_cannot_change_output_pin_state_in_memory_dict_labels_manager(self):
        self._test_cannot_change_output_pin_state('in_memory_dict_labels_manager')

    def _test_cannot_change_output_pin_state(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Output 0'
        enabled = local_io_manager.device_pin_is_enabled(device_name, pin_name)
        with assert_raises(RuntimeError):
            if enabled:
                local_io_manager.deactivate_device_input_pin(device_name, pin_name)
            else:
                local_io_manager.activate_device_input_pin(device_name, pin_name)
        assert local_io_manager.device_pin_is_enabled(device_name, pin_name) == enabled

    def test_cannot_rewire_missing_device_json_file_labels_manager(self):
        self._test_cannot_rewire_missing_device('json_file_labels_manager')

    def test_cannot_rewire_missing_device_in_memory_dict_labels_manager(self):
        self._test_cannot_rewire_missing_device('in_memory_dict_labels_manager')

    def _test_cannot_rewire_missing_device(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        device_name = 'No such device'
        pin_name = 'Some pin'
        with assert_raises(DeviceNotFound):
            local_rewiring_manager.disconnect_device_pin(device_name, pin_name)
        for channel_attrs in local_rewiring_manager.list_connections():
            assert channel_attrs.device_name != device_name
            assert channel_attrs.pin_name != pin_name

    def test_cannot_control_missing_device_json_file_labels_manager(self):
        self._test_cannot_control_missing_device('json_file_labels_manager')

    def test_cannot_control_missing_device_in_memory_dict_labels_manager(self):
        self._test_cannot_control_missing_device('in_memory_dict_labels_manager')

    def _test_cannot_control_missing_device(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'No such device'
        pin_name = 'Some pin'
        with assert_raises(DeviceNotFound):
            local_io_manager.activate_device_input_pin(device_name, pin_name)
        with assert_raises(DeviceNotFound):
            local_io_manager.deactivate_device_input_pin(device_name, pin_name)
        with assert_raises(DeviceNotFound):
            local_io_manager.device_pin_is_enabled(device_name, pin_name)

    def test_cannot_rewire_missing_channel_json_file_labels_manager(self):
        self._test_cannot_rewire_missing_channel('json_file_labels_manager')

    def test_cannot_rewire_missing_channel_in_memory_dict_labels_manager(self):
        self._test_cannot_rewire_missing_channel('in_memory_dict_labels_manager')

    def _test_cannot_rewire_missing_channel(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Input 0'
        channel = 42
        with assert_raises(ChannelNotFound):
            local_rewiring_manager.connect_device_input_pin(device_name, pin_name, channel)
        for channel_attrs in local_rewiring_manager.list_connections():
            if channel_attrs.device_name != device_name:
                continue
            assert channel_attrs.channel != channel

    def test_cannot_control_missing_pin_json_file_labels_manager(self):
        self._test_cannot_control_missing_pin('json_file_labels_manager')

    def test_cannot_control_missing_pin_in_memory_dict_labels_manager(self):
        self._test_cannot_control_missing_pin('in_memory_dict_labels_manager')

    def _test_cannot_control_missing_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_io_manager = LocalIoManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'New_Input'
        with assert_raises(PinNotFound):
            local_io_manager.activate_device_input_pin(device_name, pin_name)
        with assert_raises(PinNotFound):
            local_io_manager.deactivate_device_input_pin(device_name, pin_name)
        with assert_raises(PinNotFound):
            local_io_manager.device_pin_is_enabled(device_name, pin_name)

    def _connection_exists(self, connections_list, device_name, pin_name, channel=None):
        for ch_attrs in connections_list:
            if ch_attrs.device_name == device_name:
                if ch_attrs.pin_name == pin_name:
                    if channel is None:
                        return True
                    elif ch_attrs.channel == channel:
                        return True
        return False

    def test_connect_new_output_pin_json_file_labels_manager(self):
        self._test_connect_new_output_pin('json_file_labels_manager')

    def test_connect_new_output_pin_in_memory_dict_labels_manager(self):
        self._test_connect_new_output_pin('in_memory_dict_labels_manager')

    def _test_connect_new_output_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'New_Out'
        channel = 11
        local_rewiring_manager.connect_device_output_pin(device_name, pin_name, channel)
        assert self._connection_exists(local_rewiring_manager.list_connections(), device_name, pin_name, channel)

    def test_connect_new_input_pin_json_file_labels_manager(self):
        self._test_connect_new_input_pin('json_file_labels_manager')

    def test_connect_new_input_pin_in_memory_dict_labels_manager(self):
        self._test_connect_new_input_pin('in_memory_dict_labels_manager')

    def _test_connect_new_input_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'New_In'
        channel = 12
        local_rewiring_manager.connect_device_input_pin(device_name, pin_name, channel)
        assert self._connection_exists(local_rewiring_manager.list_connections(), device_name, pin_name, channel)

    def test_disconnect_device_pin_json_file_labels_manager(self):
        self._test_disconnect_device_pin('json_file_labels_manager')

    def test_disconnect_device_pin_in_memory_dict_labels_manager(self):
        self._test_disconnect_device_pin('in_memory_dict_labels_manager')

    def _test_disconnect_device_pin(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        device_name = 'Test_cam'
        pin_name = 'Output 0'
        local_rewiring_manager.disconnect_device_pin(device_name, pin_name)
        assert not self._connection_exists(local_rewiring_manager.list_connections(), device_name, pin_name)

    def test_fix_channel_mode_json_file_labels_manager(self):
        self._test_fix_channel_mode('json_file_labels_manager')

    def test_fix_channel_mode_in_memory_dict_labels_manager(self):
        self._test_fix_channel_mode('in_memory_dict_labels_manager')

    def _test_fix_channel_mode(self, labels_manager_type):
        labels_manager = self._labels_manager(labels_manager_type)
        virtual_gpio_device = self._virtual_gpio_device()
        local_rewiring_manager = LocalRewiringManager(labels_manager, virtual_gpio_device)
        channel = 2
        local_rewiring_manager.fix_channel_mode(channel)
        for channel_attrs in local_rewiring_manager.list_connections():
            if channel_attrs.channel == channel:
                assert channel_attrs.channel_mode == ChannelMode.OUT
                break
