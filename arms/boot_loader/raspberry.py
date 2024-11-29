# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from arms.boot_loader.interface import TFTPBootloader
from arms.kernel_arguments import LinuxKernelArguments
from arms.tftp_roots_storage import TFTPRoot


class RaspberryTFTPBootloader(TFTPBootloader):

    def __init__(self, local_ip: str, serial: str):
        try:
            int_serial = int(serial, base=16)
        except ValueError:
            raise RuntimeError(f"Serial must be a 32 bit integer in hex form. {serial!r} received")
        if not 0 < int_serial < 2 ** 32:
            raise RuntimeError(f"Serial must be a 32 bit integer in hex form. {serial!r} received")
        self._serial = serial
        self._local_ip = local_ip
        self._kernel_arguments = (
            ('console', 'serial0,115200'),
            ('console', 'tty1'),
            ('ip', f'::::{serial}:eth0:dhcp'),
            )

    def apply(self, tftp_root: TFTPRoot, kernel_arguments: LinuxKernelArguments):
        tftp_root.set_for(self._local_ip)
        cmdline_file = f'{self._serial}/cmdline.txt'
        final_kernel_arguments = kernel_arguments.with_arguments(*self._kernel_arguments)
        with tftp_root.created_file(cmdline_file) as wd:
            wd.write(final_kernel_arguments.as_line().encode('utf-8') + b'\n')
