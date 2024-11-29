# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from typing import BinaryIO

from arms.boot_loader.interface import TFTPBootloader
from arms.kernel_arguments import LinuxKernelArguments
from arms.tftp_roots_storage import TFTPRoot


# Orin Nano uses grubnet bootloader.
# See: https://docs.nvidia.com/jetson/archives/r35.4.1/DeveloperGuide/text/SD/FlashingSupport.html?highlight=cpio#configuring-a-pxe-boot-server-for-uefi-bootloader-on-jetson
# See: https://www.unixdude.net/posts/2021/Apr/23/pxe-booting-on-arm64/
# See: https://www.gnu.org/software/grub/manual/grub/html_node/Network.html
class OrinNanoTFTPBootloader(TFTPBootloader):

    def __init__(self, local_ip: str, mac: str):
        self._kernel_arguments = (
            ('rw', ''),
            ('netdevwait', ''),
            ('ip', ':::::eth0:dhcp'),
            ('fbcon', 'map:0'),
            ('net.ifnames', '0'),
            ('console', 'ttyTCU0,115200'),
            # Prevent systemd to color it's output to ensure correct display via the COM console.
            # See: https://www.freedesktop.org/software/systemd/man/latest/systemd.html#%24SYSTEMD_COLORS
            ('SYSTEMD_COLORS', '0'),
            )
        self._local_ip = local_ip
        self._mac = mac
        self._grub_config = _GrubConfig(
            _GrubVariable('timeout_style', 'hidden'),
            _GrubVariable('timeout', '0'),
            )

    def apply(self, tftp_root: TFTPRoot, kernel_arguments: LinuxKernelArguments):
        tftp_root.set_for(self._local_ip)
        final_kernel_arguments = kernel_arguments.with_arguments(*self._kernel_arguments)
        orin_nano_menu_entry = _GrubMenuEntry(
            'OrinNano',
            _GrubLinuxKernelLine('/Image.gz', final_kernel_arguments),
            _GrubLinuxInitrdLine('/initrd'),
            )
        main_grub_config_path = '/grub/grub.cfg'
        with tftp_root.created_file(main_grub_config_path) as wd:
            wd.write(_get_main_grub_cfg_text())
        device_grub_config_path = f'/grub/grub.cfg-{_normalize_to_grub_form(self._mac)}'
        grub_config = self._grub_config.add(orin_nano_menu_entry)
        with tftp_root.created_file(device_grub_config_path) as wd:
            grub_config.write_to(wd)


def _normalize_to_grub_form(mac: str) -> str:
    return mac.lower().replace("-", ":")


def _get_main_grub_cfg_text() -> bytes:
    return Path(__file__).with_name('grub.cfg').read_bytes()


class _GrubObject(metaclass=ABCMeta):

    @abstractmethod
    def write_to(self, fd: BinaryIO):
        pass


class _GrubConfig(_GrubObject):

    def __init__(self, *objects: _GrubObject):
        self._objects = objects

    def add(self, grub_object: _GrubObject) -> '_GrubConfig':
        return self.__class__(*self._objects, grub_object)

    def write_to(self, fd: BinaryIO):
        for grub_object in self._objects:
            grub_object.write_to(fd)


class _GrubVariable(_GrubObject):

    def __init__(self, name: str, value: str):
        self._name = name
        self._value = value

    def write_to(self, fd: BinaryIO):
        fd.write(f"set {self._name}={self._value}\n".encode('ascii'))


class _GrubMenuEntry(_GrubObject):

    def __init__(self, name: str, kernel: '_GrubLinuxKernelLine', initrd: '_GrubLinuxInitrdLine'):
        self._name = name
        self._kernel = kernel
        self._initrd = initrd

    def write_to(self, fd: BinaryIO):
        indent = 2
        fd.write(f'\nmenuentry {self._name!r} {{\n'.encode('ascii'))
        fd.write(b" " * indent)
        self._kernel.write_to(fd)
        fd.write(b" " * indent)
        self._initrd.write_to(fd)
        fd.write(b"}\n")


class _GrubLinuxKernelLine(_GrubObject):

    def __init__(self, path: str, arguments: LinuxKernelArguments):
        self._path = path
        self._arguments = arguments

    def write_to(self, fd: BinaryIO):
        value = f'linux {self._path} '.encode('ascii')
        arguments = self._arguments.as_line().encode('ascii')
        fd.write(value + arguments + b'\n')


class _GrubLinuxInitrdLine(_GrubObject):

    def __init__(self, path: str):
        self._path = path

    def write_to(self, fd: BinaryIO):
        fd.write(f'initrd {self._path} \n'.encode('utf-8'))
