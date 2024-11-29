# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from directories import clean_up_snapshots
from directories import get_ft_snapshots_cache_root
from directories.prerequisites import concurrent_safe_download
from vm.virtual_box._access_settings import AccessSettings
from vm.virtual_box._vbox_manage_medium import vbox_manage_create_child_medium
from vm.virtual_box._vbox_manage_medium import vbox_manage_register_medium
from vm.virtual_box._vm import VBoxVM
from vm.virtual_box._vm import VBoxVMDisk
from vm.virtual_box._vm import VBoxVMSettings
from vm.vm import VM
from vm.vm_type import VMSnapshotTemplate


class VBoxConfigurationTemplate(metaclass=ABCMeta):

    def __init__(self, name, ram_mb: int, cpu_count: int, access_settings: AccessSettings):
        self._name = name
        self._ram_mb = ram_mb
        self._cpu_count = cpu_count
        self._access_settings = access_settings

    @contextmanager
    def _vm_registered(self, disk: VBoxVMDisk):
        with self._access_settings.claimed_port_range() as [vm_index, modifyvm_params]:
            vm_name = f'ft-{vm_index:05d}'
            vm_control = VBoxVM(vm_name)
            _logger.info("Configure VM %r as %r", vm_control, self)
            vm_control.purge()
            vbox_settings = VBoxVMSettings(self._ram_mb, self._cpu_count, self._xml_stub())
            vm_control.register(disk, vbox_settings, modifyvm_params)
            try:
                yield vm_control
            finally:
                vm_control.purge()

    @abstractmethod
    def _xml_stub(self):
        pass

    def __repr__(self):
        return f'<{self.__class__.__name__} {self._cpu_count} CPU, {self._ram_mb} MB RAM>'


class VBoxSnapshotTemplate(VBoxConfigurationTemplate, VMSnapshotTemplate, metaclass=ABCMeta):

    def name(self):
        return self._name

    @contextmanager
    def vm_locked(self, snapshot_uri: str, parent_uri: Optional[str] = None) -> AbstractContextManager[VM]:
        if parent_uri is not None:
            self._get_snapshot(parent_uri)
        snapshot_path = self._get_snapshot(snapshot_uri)
        with self._vm_registered(VBoxSnapshotDiff(snapshot_path)) as vm_control:
            vm_control.power_on()
            # Such a context-agnostic function is here to force the ability to
            # create an OS Access object without much knowledge of exact VM
            # configuration. I.e. without the index for VirtualBox VMs. This
            # ability is convenient when working with VMs in manual fashion.
            os_access = vm_control.get_os_access()
            vm = VM(vm_control, os_access)
            _logger.info("VM is ready: %r", vm)
            try:
                yield vm
            finally:
                os_access.close()

    def _get_snapshot(self, snapshot_uri: str):
        clean_up_snapshots()
        local_path = concurrent_safe_download(snapshot_uri, get_ft_snapshots_cache_root())
        # WARNING: Non-documented behaviour.
        # Virtualbox implicitly removes parent images if they have no others
        # linked disks. Therefore, removal of the last linked to a template VM
        # removes this template at one.
        # As workaround set read-only mode for group and other.
        local_path.chmod(0o644)
        vbox_manage_register_medium(local_path)
        return local_path


class VBoxSnapshotDiff(VBoxVMDisk):

    def __init__(self, snapshot_path: Path):
        self._snapshot_path = snapshot_path

    def create(self, destination):
        vbox_manage_create_child_medium(self._snapshot_path, destination)


class VBoxLinux(VBoxSnapshotTemplate):

    def _xml_stub(self):
        return Path(__file__).parent / 'configuration/ubuntu.vbox'


class VBoxWindows(VBoxSnapshotTemplate):

    def _xml_stub(self):
        return Path(__file__).parent / 'configuration/win.vbox'


_logger = logging.getLogger(__name__)
