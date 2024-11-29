# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import logging
from pathlib import Path
from typing import Collection
from typing import TypeVar

from arms.boot_loader.interface import TFTPBootloader
from arms.hierarchical_storage import PendingSnapshot
from arms.kernel_arguments import LinuxKernelArguments
from arms.power_control_interface import PowerControlInterface
from arms.qcow2target_api import IscsiTarget
from arms.qcow2target_api import TargetNotExist
from arms.remote_control import ARMRemoteControl
from arms.root_fs import RemoteRootFS
from arms.tftp_roots_storage import TFTPRoot

_logger = logging.getLogger(__name__.split('.')[-1])


_R = TypeVar('_R', bound=RemoteRootFS)


class Machine:

    def __init__(
            self,
            name: str,
            power_interface: PowerControlInterface,
            remote_control: ARMRemoteControl,
            available_roots: Collection[RemoteRootFS],
            ):
        self._name = name
        self._power_interface = power_interface
        self._remote_control = remote_control
        self._available_roots = available_roots

    async def start(self):
        _logger.info("%s: Power on", self)
        await self._power_interface.power_on()

    async def shutdown(self):
        _logger.info("%s: Request graceful shutdown", self)
        remote_fs_disconnect = [root_fs.wait_disconnected() for root_fs in self._available_roots]
        await asyncio.gather(*remote_fs_disconnect, self._remote_control.shutdown())
        await self._power_interface.power_off()

    async def power_off(self):
        _logger.info("%s: Power off", self)
        remote_fs_disconnect = [root_fs.wait_disconnected() for root_fs in self._available_roots]
        await asyncio.gather(*remote_fs_disconnect, self._power_interface.power_off())

    def get_root_fs(self, root_fs_class: type[_R]) -> _R:
        for root_fs in self._available_roots:
            if isinstance(root_fs, root_fs_class):
                return root_fs
        raise RuntimeError(
            f"{self}: Can't handle root FS {root_fs_class!r}. Available {self._available_roots}")

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._name}>"


class RunningMachine:

    def __init__(self, machine: Machine, current_disk: PendingSnapshot, remote_root: RemoteRootFS):
        self._machine = machine
        self._current_disk = current_disk
        self._remote_root = remote_root

    async def commit(self) -> Machine:
        _logger.info("%s: Commit %s", self._machine, self._current_disk)
        await self._machine.shutdown()
        await self._remote_root.detach_disk()
        self._current_disk.commit()
        return self._machine

    async def rollback(self) -> Machine:
        _logger.info("%s: Rollback %s", self._machine, self._current_disk)
        await self._machine.power_off()
        await self._remote_root.detach_disk()
        self._current_disk.rollback()
        return self._machine

    def __repr__(self):
        return f'<Running {self._machine}>'


class ISCSIExt4Root(RemoteRootFS):

    def __init__(self, server_ip: str, server_port: int, machine_id: str):
        self._server_ip = server_ip
        self._server_port = server_port
        if blocked_chars := {'_', '='}.intersection(machine_id):
            raise RuntimeError(f"Target name {machine_id} MUST NOT contain {blocked_chars}")
        self._target_name = f"iqn.2008-05.com.networkoptix.ft.arms:{machine_id}"
        self._initiator_name = f"iqn.arm.initiator:{machine_id}"
        self._target = IscsiTarget(self._target_name)

    def get_arguments(self) -> LinuxKernelArguments:
        return LinuxKernelArguments(
            ('root', 'LABEL=rootfs'),
            ('ISCSI_INITIATOR', self._initiator_name),
            ('ISCSI_TARGET_NAME', self._target_name),
            ('ISCSI_TARGET_IP', self._server_ip),
            ('ISCSI_TARGET_PORT', str(self._server_port)),
            ('rootfstype', 'ext4'),
            ('fsck.repair', 'yes'),
            ('rootwait', '10'),
            )

    async def detach_disk(self):
        try:
            await self._target.detach_block_device()
        except TargetNotExist:
            _logger.info("%s: %s not exists", self, self._target)

    async def attach_disk(self, path: Path):
        try:
            await self._target.attach_block_device(path)
        except TargetNotExist:
            _logger.info("%s: %s not exists. Create it and attach %s", self, self._target, path)
            await self._target.create()
            await self._target.attach_block_device(path)

    async def wait_disconnected(self):
        try:
            await self._target.wait_disconnected()
        except TargetNotExist:
            _logger.info("%s: %s not exists", self, self._target)

    def __repr__(self):
        return f'<ISCSI Root {self._target_name}>'


class PXEMachine(Machine):

    def __init__(
            self,
            name: str,
            power_interface: PowerControlInterface,
            remote_control: ARMRemoteControl,
            tftp_boot_loader: 'TFTPBootloader',
            available_roots: Collection[RemoteRootFS],
            ):
        super().__init__(name, power_interface, remote_control, available_roots)
        self._tftp_boot_loader = tftp_boot_loader

    def config_tftp(self, tftp_root: TFTPRoot, kernel_arguments: LinuxKernelArguments):
        self._tftp_boot_loader.apply(tftp_root, kernel_arguments)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._name}>'
