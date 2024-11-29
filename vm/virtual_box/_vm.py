# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import io
import json
import logging
import os
import re
import shutil
import time
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from datetime import timezone
from enum import Enum
from pathlib import Path
from typing import Mapping
from typing import Sequence
from urllib.parse import urlparse
from uuid import uuid4
from xml.etree import cElementTree as ElementTree

from directories import get_ft_snapshots_origin_root
from directories import make_artifact_store
from os_access import OsAccess
from os_access import PosixAccess
from os_access import WindowsAccess
from vm.hypervisor import PortMap
from vm.hypervisor import VMScreenCannotSetMode
from vm.hypervisor import Vm
from vm.hypervisor import VmNotFound
from vm.virtual_box._access_settings import get_port_forwarding_table
from vm.virtual_box._disk_exceptions import DiskExists
from vm.virtual_box._hypervisor_exceptions import VirtualBoxError
from vm.virtual_box._hypervisor_exceptions import VirtualBoxGuestAdditionsNotReady
from vm.virtual_box._hypervisor_exceptions import VirtualBoxVMNotReady
from vm.virtual_box._hypervisor_exceptions import virtual_box_error_cls
from vm.virtual_box._vbox_manage_medium import _vbox_get_medium_description
from vm.virtual_box._vbox_manage_medium import _vbox_set_medium_description
from vm.virtual_box._vbox_manage_medium import vbox_manage_close_medium
from vm.virtual_box._vbox_manage_medium import vbox_manage_create_medium
from vm.virtual_box._vboxmanage import get_virtual_box
from vm.virtual_box._vboxmanage import vbox_default_dir
from vm.virtual_box._vboxmanage import vboxmanage
from vm.virtual_box._vboxmanage import vboxmanage_locked
from vm.virtual_box._vboxmanage import vboxmanage_until_success
from vm.virtual_box._vm_networking import INTERNAL_NIC_INDICES
from vm.virtual_box._vm_networking import bandwidth_group
from vm.virtual_box._vm_networking import host_network_interfaces
from vm.virtual_box._vm_networking import nic_pci_slots
from vm.virtual_box._vm_networking import nic_slots


class VBoxVM(Vm):

    def __init__(self, vm_name: str):
        """Name is merely for better logging: it's not checked here."""
        super(VBoxVM, self).__init__(vm_name)
        # Mimic structure of ~/Virtual Box VMs. If settings files were placed into a single folder,
        # logs and snapshots from all VMs would be in the same folder.
        # TODO: Make the dir and define structure in VirtualBox component.
        machines_dir = vbox_default_dir()
        self._disk_file = machines_dir / (self.name + '.vdi')
        self._dir = machines_dir / self.name
        self._settings_file = self._dir / (self.name + '.vbox')
        self._logs_dir = self._dir / 'Logs'

    def register(self, disk: 'VBoxVMDisk', vbox_settings: 'VBoxVMSettings', modifyvm_params: Sequence[str]):
        self.dir().mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(vbox_settings.render(self.name, self._logs_dir))
        vboxmanage(['registervm', str(self._settings_file)])
        vboxmanage(['modifyvm', self.name, *modifyvm_params])
        disk.create(self._disk_file)
        vboxmanage([
            'storageattach', self.name, '--storagectl', 'SATA',
            '--device', '0', '--port', '0', '--type', 'hdd',
            '--medium', str(self._disk_file),
            ])

    def get_os_access(self) -> OsAccess:
        if self.os_name() == 'Windows':
            return WindowsAccess(
                self.ip_address(),
                'Administrator',
                self.metadata().get('password', 'WellKnownPassword1!@#'),
                port_map=self.port_map(),
                )
        else:
            return PosixAccess.to_vm(
                'root',
                Path(__file__).parent.parent.parent.joinpath('_internal/virtual_box.rsa.key').read_text(),
                address=self.ip_address(),
                port_map=self.port_map(),
                )

    def port_map(self):
        result = {'tcp': {}, 'udp': {}}
        for port in get_port_forwarding_table(self._info()):
            result[port.protocol][port.guest_port] = port.host_port
        return PortMap(**result)

    def ip_address(self) -> str:
        return '127.0.0.1'

    def dir(self):
        return self._dir

    def metadata(self) -> Mapping[str, str]:
        raw = _vbox_get_medium_description(self._disk_file)
        return json.loads(raw) if raw else {}

    def _info(self) -> Mapping[str, str]:
        """Obtain VM info and wrap in an object. May take a few seconds.

        This command is prone to fail with the VirtualBoxVMNotReady exception
        at the shutdown or poweroff, when called many times per second.

        A retry request after a short delay usually is successful.
        """
        command = ['showvminfo', str(self.name), '--machinereadable']
        attempts_left = 5
        while True:
            try:
                raw_output = vboxmanage_until_success(command)
            except VirtualBoxError as err:
                error_message = str(err).strip()
                if not error_message:
                    logging.warning("An unknown mute error has happened")
                elif 'Operation aborted' in error_message:
                    logging.warning("Operation aborted error has happened")
                elif 'Access denied' in error_message:
                    logging.warning("Access denied error has happened")
                elif 'Unexpected error' in error_message:
                    logging.warning("An unexpected error has happened")
                elif 'Instance not initialized' in error_message:
                    logging.warning("An 'Instance is not initialized' error has occurred")
                else:
                    raise
                if attempts_left > 0:
                    logging.info("Retry %s. Attempts left: %s", command, attempts_left)
                    attempts_left -= 1
                    time.sleep(0.25)
                    continue
                raise
            _logger.debug("Parse raw VM info of %s.", self.name)
            return dict(_VmInfoParser(raw_output))

    def __repr__(self):
        return f'<VBox VM {self.name}>'

    def _remove_additional_disks(self):
        # Image files and registered disks exist independently of each other.
        # System disk is outside of self.dir.
        for additional_disk_path in self._dir.glob('*.vdi'):
            vbox_manage_close_medium(additional_disk_path)

    def purge(self):
        try:
            self.power_off()
        except virtual_box_error_cls('E_ACCESSDENIED'):
            _logger.warning("Machine inaccessible: %r", self)
        except VmNotFound:
            _logger.debug("VM %s is not registered", self.name)
        else:
            self._unregister()
        # Deleting disk via vbox_manage_close_medium() can fail with error
        # E_FAIL: Parent medium is not found in the media registry, because
        # VM unregister removes parent snapshot, if VM disk was the only child.
        # Delete VM disk as a file instead.
        if self._disk_file.exists():
            get_virtual_box().fix_permissions(self._disk_file)
            self._disk_file.unlink()
        try:
            self._settings_file.unlink()
        except FileNotFoundError:
            _logger.info("File doesn't exist: %s", self._settings_file)
        else:
            _logger.info("File has been deleted: %s", self._settings_file)
        self._remove_additional_disks()

    def reset(self):
        _logger.info("%s: Reset", self)
        vboxmanage(['controlvm', self.name, 'reset'])

    def _is_off(self):
        try:
            return self._info()['VMState'] in {'poweroff', 'aborted'}
        except KeyError:
            return False

    def power_on(self):
        command = [
            'startvm', self.name,
            '--type', 'headless',
            '-E', 'VBOX_RELEASE_LOG_FLAGS="pid thread group flag time timeprog"',
            '-E', 'VBOX_RELEASE_LOG="+all.enabled.level12.flow.restrict,+intnet.enabled.level12.flow.restrict"',
            ]
        attempt = 1
        while True:
            try:
                # Starting multiple VBoxHeadless processes simultaneously can
                # fail with NS_ERROR_FAILURE: The VM session was aborted.
                # See https://forums.virtualbox.org/viewtopic.php?t=109983
                # See https://www.virtualbox.org/ticket/21814
                # Use locked VBoxManage to start a VM to prevent such errors.
                vboxmanage_locked(command)
                break
            except virtual_box_error_cls('E_FAIL') as e:
                latest_error = str(e)
                if str(e) == 'The VM session was closed before any attempt to power it on':
                    _logger.info("Could not power on machine %r since VBoxSvc is shutting down", self)
                elif str(e) == "Implementation of the USB 3.0 controller not found!":
                    raise RuntimeError("VirtualBox Extension Pack is not installed")
                else:
                    raise
            if attempt > 10:
                raise RuntimeError(
                    f"Failed to power on VM after {attempt} attempts. "
                    f"Latest error: {latest_error}")
            attempt += 1
            time.sleep(0.5)

    def power_off(self):
        attempt = 1
        while True:
            _logger.debug("Power off %s: attempt %d", self.name, attempt)
            try:
                vboxmanage(['controlvm', self.name, 'poweroff'])
            except VirtualBoxError as e:
                latest_error = str(e)
                if 'is not currently running' in str(e):
                    break
                elif 'The virtual machine is being powered down' in str(e):
                    _logger.info("%s is being powering down", self)
                elif 'Failed to get a console object from the direct session' in str(e):
                    _logger.warning("Failed to get a console object for %s", self)
                elif 'Could not find a registered machine' in str(e):
                    raise VmNotFound(f"Cannot find VM: {self.name}")
                elif 'extended info not available' in str(e):
                    raise RuntimeError(
                        f"Can't shutdown a VM {self.name} due to a general error. "
                        "Possibly, the VM has gone into the Guru Meditation state. "
                        "Consider to resolve the problem manually")
                else:
                    raise
            else:
                latest_error = None
            if attempt > 10:
                raise RuntimeError(
                    f"Failed to power off VM after {attempt} attempts. "
                    f"Latest error: {latest_error}")
            attempt += 1
            time.sleep(0.5)

    def os_name(self) -> str:
        if 'Windows' in self._info()['ostype']:
            return 'Windows'
        else:
            return 'Linux'

    def plug_internal(self, network_name: str):
        slot = self._free_nics()[0]
        # Reportedly, setting link state first can halt traffic to and from the VM.
        vboxmanage([
            'controlvm', self.name,
            f'nic{slot}', 'intnet', f'{network_name}-{os.getpid()}',
            ])
        nic_id = nic_pci_slots[slot]
        self.connect_cable(nic_id)
        return nic_id

    def plug_bridged(self, host_nic_name):
        host_nics = host_network_interfaces()
        if host_nic_name not in host_nics:
            raise RuntimeError(f"{host_nic_name} is not among {host_nics}")
        slot = self._free_nics()[0]
        # It appears that in VirtualBox 7.0 a bridged network could not be connected
        # by a single command as it is done for internal networks.
        # Order matters: when NIC type is set before `setlinkstate`, NIC becomes unresponsive.
        self._manage_nic_on_powered_on_vm(slot, 'setlinkstate', 'on')
        self._manage_nic_on_powered_on_vm(slot, 'nic', 'bridged', host_nic_name)
        return nic_pci_slots[slot]

    def _free_nics(self) -> Sequence[int]:
        result = []
        for nic_index in INTERNAL_NIC_INDICES:
            nic_id = nic_pci_slots[nic_index]
            nic_type = self._info()['nic{}'.format(nic_index)]
            _logger.debug("NIC %d (%s): %s", nic_index, nic_id, nic_type)
            assert nic_type != 'none'
            if nic_type == 'null':
                result.append(nic_index)
        result.sort()  # Make the order predictable.
        return result

    def _limit_nic_bandwidth(self, group, speed_limit_kbit):
        """Limit network adapter bandwidth.

        See: https://www.virtualbox.org/manual/ch06.html#network_bandwidth_limit:

        > The limits for each group can be changed while the VM is running, with changes being
        picked up immediately. The example below changes the limit for the group created in the
        example above to 100 Kbit/s:
        ```{.sh}
        VBoxManage bandwidthctl "VM name" set network1 --limit 100k
        ```

        In `./configure-vm.sh`, each NIC gets its own bandwidth group, `network1`, `network2`...
        """
        vboxmanage([
            'bandwidthctl', self.name,
            'set', group,
            '--limit', '{}k'.format(speed_limit_kbit)])

    def limit_bandwidth(self, speed_limit_kbit):
        for nic_index in INTERNAL_NIC_INDICES:
            name = bandwidth_group(nic_index)
            self._limit_nic_bandwidth(name, speed_limit_kbit)

    def _manage_nic_on_powered_on_vm(self, nic_index, command, *arguments):
        prefix = ['controlvm', self.name, f'{command}{nic_index}']
        vboxmanage(prefix + list(arguments))

    def _manage_storage(self, port, args):
        vboxmanage([
            'storageattach', self.name,
            '--port', str(port),
            *args])

    def _get_free_disk_port(self, interface_type: str) -> int:
        for key, value in self._info().items():
            match = re.match(r'^(?P<controller_type>(SATA|USB))-(?P<port>\d)-\d$', key)
            if match is None:
                continue
            if match.group('controller_type') != interface_type:
                continue
            if value != 'none':
                continue
            return int(match.group('port'))
        raise RuntimeError("All ports are busy")

    def add_disk(self, controller_type, size_mb):
        controller_type = controller_type.upper()
        if controller_type not in ['USB', 'SATA']:
            raise ValueError("Interface must be 'USB' or 'SATA'.")
        port = self._get_free_disk_port(controller_type)
        path = self._dir / f'{controller_type}{port}.vdi'
        vbox_manage_create_medium(str(path), size_mb)
        self._manage_storage(port, [
            '--type', 'hdd',
            '--storagectl', controller_type,
            '--medium', str(path),
            # On running VMs, --hotpluggable makes medium UUID associated with
            # the VM, locked and impossible to unregister and close.
            # '--hotpluggable', 'on',
            ])

    def add_disk_limited(self, controller_type: str, size_mb: int, speed_limit_mbs: int):
        if not self._is_off():
            raise RuntimeError("The VM must be powered off before appending disk with a speed limit")
        controller_type = controller_type.upper()
        if controller_type not in ['USB', 'SATA']:
            raise ValueError("Interface must be 'USB' or 'SATA'")
        port = self._get_free_disk_port(controller_type)
        path = self._dir / f'{controller_type}{port}.vdi'
        vbox_manage_create_medium(str(path), size_mb)
        bandwidth_disk_group = f'{controller_type}{port}'
        vboxmanage_locked([
            'bandwidthctl', self.name,
            'add', bandwidth_disk_group,
            '--type', 'disk',
            '--limit', f'{speed_limit_mbs}M',
            ])
        self._manage_storage(port, [
            '--type', 'hdd',
            '--storagectl', controller_type,
            '--medium', str(path),
            '--bandwidthgroup', bandwidth_disk_group,
            ])

    def connect_cable(self, nic_id):
        nic_index = nic_slots[nic_id]
        self._manage_nic_on_powered_on_vm(nic_index, 'setlinkstate', 'on')

    def disconnect_cable(self, nic_id):
        nic_index = nic_slots[nic_id]
        self._manage_nic_on_powered_on_vm(nic_index, 'setlinkstate', 'off')

    def copy_logs(self, destination):
        vbox_env = get_virtual_box()
        vbox_env.fix_permissions(self._logs_dir)
        vm_logs_dir = destination / self.name
        vm_logs_dir.mkdir(exist_ok=True)
        for log_file in self._logs_dir.glob('*'):  # Excludes starting with dot.
            dest = vm_logs_dir / log_file.name
            _logger.debug("Copy %s to %s", log_file, dest)
            shutil.copy(log_file, vm_logs_dir)

    def wait_off(self, timeout_sec=30):
        end_at = time.monotonic() + timeout_sec
        while time.monotonic() < end_at:
            if self._is_off():
                return
            _logger.info(
                "Waiting for %r shutdown, seconds left: %.1f",
                self, max(.0, end_at - time.monotonic()))
            time.sleep(1.0)
        else:
            raise TimeoutError("Timed out waiting for shutdown: {}".format(self))

    def shutdown(self, timeout_sec=30):
        _logger.info('Shutdown %s', self)
        shutdown_command = ['controlvm', self.name, 'acpipowerbutton']
        try:
            vboxmanage(shutdown_command)
        except VirtualBoxError as e:
            if 'is not currently running' in str(e):
                return
            return
        self.wait_off(timeout_sec=timeout_sec)

    def save_as_base_snapshot(self, os_name: str, metadata: Mapping[str, str]) -> str:
        result_name = f'{os_name}-{datetime.now(tz=timezone.utc):%Y%m%d%H%M%S}.vdi'
        images_path = Path('~/.cache/nxft-base-snapshots').expanduser()
        images_path.mkdir(parents=True, exist_ok=True)
        result_disk = images_path.joinpath(result_name)
        self._save_as_snapshot(result_disk)
        _vbox_set_medium_description(result_disk, json.dumps(metadata))
        _make_disk_md5(result_disk)
        result_disk.chmod(0o444)  # base image should be read-only
        return make_artifact_store().store_one(result_disk)

    def save_as_plugin_snapshot(self, parent_snapshot_uri: str, plugin_id: str):
        timestamp = datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')
        [_, name] = os.path.split(urlparse(parent_snapshot_uri).path)
        result_name = '--'.join([plugin_id, timestamp, name])
        result_disk = get_ft_snapshots_origin_root() / result_name
        self._save_as_snapshot(result_disk)
        _make_disk_md5(result_disk)
        result_disk.chmod(0o644)
        return make_artifact_store().store_one(result_disk)

    def _save_as_snapshot(self, destination: Path):
        vboxmanage(['modifymedium', 'disk', str(self._disk_file), '--compact'])
        self._unregister()
        _logger.info("Delete file: %s", self._settings_file)
        try:
            self._settings_file.unlink()
        except FileNotFoundError:
            _logger.warning("File doesn't exist: %s", self._settings_file)
        else:
            _logger.debug("Deleted: %s", self._settings_file)
        if destination.exists():
            raise DiskExists(f"Cannot move {self} to {destination} because it exists")
        _logger.info("Calculate MD5: %s", self._disk_file)
        get_virtual_box().fix_permissions(self._disk_file)
        if destination.suffix != '.vdi':
            raise RuntimeError(f"{destination} is not a VirtualBox disk")
        _logger.info("%s: Load from %s", destination, self._disk_file)
        # Path.replace() will preserve file ownership and permissions.
        # Snapshot is created under ft-1xx user, and ft user cannot change
        # its ownership. Main user ownership is required to set read-only
        # permissions for a group to prevent VirtualBox from deleting snapshot.
        # Read from self._disk_file and write to the destination instead of replace.
        shutil.copyfile(self._disk_file, destination)
        _logger.debug("%s: Successfully loaded", self)

    def _unregister(self):
        for _ in range(10):
            try:
                vboxmanage(['unregistervm', self.name])
            except VirtualBoxVMNotReady:
                _logger.warning("Not ready, try again in a while: %r", self)
            except virtual_box_error_cls('E_ACCESSDENIED'):
                _logger.warning("Access denied, try again in a while: %r", self)
            except virtual_box_error_cls('VBOX_E_OBJECT_NOT_FOUND'):
                _logger.warning("Not found, assume it's been deleted: %r", self)
                break
            else:
                _logger.debug("Deleted normally: %r", self)
                break
            time.sleep(1)

    def take_screenshot(self, file):
        _logger.info("%s: Take screenshot into %s", self, file)
        if file.suffix != '.png':
            raise RuntimeError("Only PNG format is supported")
        screenshot_path = self._logs_dir / file.name
        vboxmanage(['controlvm', self.name, 'screenshotpng', str(screenshot_path)])
        # Fix permissions on logs folder, otherwise screenshot will fail to copy.
        get_virtual_box().fix_permissions(screenshot_path.parent)
        shutil.copy(screenshot_path, file)
        screenshot_path.unlink()

    def set_screen_mode(self, width: int, height: int, color_depth: int):
        vm = VBoxVM(self.name)
        try:
            vm._wait_until_guest_additions_loaded(_GuestAdditionsRunLevel.DESKTOP)
        except VirtualBoxGuestAdditionsNotReady:
            raise VMScreenCannotSetMode(
                f"{self.name}: Cannot set screen mode; guest additions are not fully loaded")
        command = [
            'controlvm', self.name,
            'setvideomodehint', str(width), str(height), str(color_depth),
            ]
        vboxmanage(command)
        finished_at = time.monotonic() + 5
        while True:
            [width_current, height_current, color_depth_current] = self._get_screen_parameters()
            if width == width_current and height == height_current and color_depth == color_depth_current:
                break
            time.sleep(1)
            if time.monotonic() > finished_at:
                raise VMScreenCannotSetMode(
                    f"{self.name}: Cannot set screen mode {width}x{height}x{color_depth},"
                    f" got {width_current}x{height_current}x{color_depth_current}")

    def _get_screen_parameters(self) -> tuple[int, int, int]:
        vm_info = self._info()
        # The VideoMode variable looks like this: 1024,768,32"@0,0 1
        [w_h_color, *_] = vm_info['VideoMode'].split('"@')
        [width, height, color_depth] = w_h_color.split(',')
        return int(width), int(height), int(color_depth)

    def _get_guest_additions_run_level(self) -> '_GuestAdditionsRunLevel':
        vm_info = self._info()
        guest_additions_run_level = int(vm_info['GuestAdditionsRunLevel'])
        return _GuestAdditionsRunLevel(guest_additions_run_level)

    def _wait_until_guest_additions_loaded(self, expected_state: '_GuestAdditionsRunLevel', timeout: float = 15):
        finished_at = time.monotonic() + timeout
        while True:
            guest_additions_run_level = self._get_guest_additions_run_level()
            if guest_additions_run_level == expected_state:
                return
            if time.monotonic() > finished_at:
                raise VirtualBoxGuestAdditionsNotReady(
                    "Timed out waiting for Guest Additions to be fully loaded. "
                    f"There is should be state DESKTOP, but got {guest_additions_run_level.name}")
            time.sleep(1.0)


class VBoxVMDisk(metaclass=ABCMeta):

    @abstractmethod
    def create(self, destination: Path):
        pass


class _VmInfoParser:
    """Single reason why it exists is multiline description."""

    def __init__(self, raw_output):
        self._data = raw_output + '\n'  # Sentinel.
        self._pos = 0

    def _read_element(self, symbol_after):
        if self._data[self._pos] == '"':
            return self._read_quoted(symbol_after)
        else:
            return self._read_bare(symbol_after)

    def _read_bare(self, symbol_after):
        begin = self._pos
        self._pos = self._data.find(symbol_after, begin)
        end = self._pos
        self._pos += len(symbol_after)
        return self._data[begin:end]

    def _read_quoted(self, symbol_after):
        self._pos += 1
        begin = self._pos
        self._pos = self._data.find('"' + symbol_after, begin)
        end = self._pos
        self._pos += 1 + len(symbol_after)
        return self._data[begin:end]

    def _read_key(self):
        return self._read_element('=')

    def _read_value(self):
        return self._read_element('\n')

    def __iter__(self):
        while self._pos < len(self._data):
            key = self._read_key()
            value = self._read_value()
            yield key, value


class VBoxVMSettings:

    def __init__(self, ram_mb: int, cpu_count: int, xml_template_path: Path):
        self._ram_mb = ram_mb
        self._cpu_count = cpu_count
        self._xml_template_path = xml_template_path

    def render(self, vm_name: str, boot_log_dir: Path):
        tree = ElementTree.parse(self._xml_template_path)
        machine = tree.find('./vbox:Machine', _xml_ns)
        machine.attrib['name'] = vm_name
        machine.attrib['uuid'] = str(uuid4())
        cpu = tree.find('./vbox:Machine/vbox:Hardware/vbox:CPU', _xml_ns)
        cpu.attrib['count'] = str(self._cpu_count)
        memory = tree.find('./vbox:Machine/vbox:Hardware/vbox:Memory', _xml_ns)
        memory.attrib['RAMSize'] = str(self._ram_mb)
        network = machine.find('./vbox:Hardware/vbox:Network', _xml_ns)
        adapters = network.findall('./vbox:Adapter', _xml_ns)
        for index, adapter in enumerate(adapters):
            mac = hashlib.md5()
            mac.update(vm_name.encode('utf-8'))
            mac.update(index.to_bytes(1, byteorder='little', signed=False))
            mac = int(mac.hexdigest(), 16) & 0xFE_FF_FF_FF_FF_FF
            mac = f'{mac:012x}'
            adapter.attrib['MACAddress'] = mac
        serial_port = tree.find('./vbox:Machine/vbox:Hardware/vbox:UART/vbox:Port', _xml_ns)
        if serial_port is not None:
            serial_port.attrib['path'] = str(boot_log_dir / 'boot.log')
        for elem in tree.iter():
            elem.attrib = _qualify_attributes(elem.attrib, _xml_ns['vbox'])
        stream = io.BytesIO()
        # XML declaration and whitespace adjustments ease XML files comparison.
        stream.write(b'<?xml version="1.0"?>\n')
        tree.write(stream, encoding='utf-8', default_namespace=_xml_ns['vbox'])
        stream.write(b'\n')
        return stream.getvalue().replace(b' />', b'/>').decode()


def _qualify_attributes(attrib: Mapping[str, str], ns: str):
    """Work around unqualified attributes with default_namespace (Python bug).

    This error is known to be a bug in Python's ElementTree module. The XML
    specification states that default namespaces do not apply to attribute
    names, but the error suggests that the ElementTree module incorrectly
    rejects non-qualified names when the default_namespace option is used.

    See: https://github.com/python/cpython/issues/61290

    >>> _qualify_attributes({'{n}k': 'v', 'kk': 'vv'}, 'nn')
    {'{n}k': 'v', '{nn}kk': 'vv'}
    """
    new_attrib = {}
    for key in attrib:
        if not key.startswith('{'):
            qualified = '{' + ns + '}' + key
        else:
            qualified = key
        new_attrib[qualified] = attrib[key]
    return new_attrib


class _GuestAdditionsRunLevel(Enum):

    # See at VirtualBox source file: src\VBox\Main\idl\VirtualBox.xidl
    NONE = 0  # Guest Additions are not loaded.
    SYSTEM = 1  # Guest drivers are loaded.
    USERLAND = 2  # Common components (such as application services) are loaded.
    DESKTOP = 3  # Per-user desktop components are loaded.


def _make_disk_md5(disk_path: Path) -> Path:
    chunk_size_bytes = 1024 * 1024  # Fastest
    md5_hash = hashlib.md5()
    with disk_path.open("rb") as src:
        for chunk in iter(lambda: src.read(chunk_size_bytes), b''):
            md5_hash.update(chunk)
    checksum = md5_hash.hexdigest()
    md5_file = disk_path.with_suffix(disk_path.suffix + '.md5')
    md5_file.write_text(f"{checksum} {disk_path.name}\n")
    return md5_file


_logger = logging.getLogger(__name__)
_xml_ns = {'vbox': 'http://www.virtualbox.org/'}
