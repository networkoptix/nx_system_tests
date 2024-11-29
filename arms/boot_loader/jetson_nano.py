# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from pathlib import Path

from arms.boot_loader.interface import TFTPBootloader
from arms.kernel_arguments import LinuxKernelArguments
from arms.tftp_roots_storage import TFTPRoot


class JetsonNanoTFTPBootloader(TFTPBootloader):

    def __init__(self, local_ip: str, mac: str):
        self._kernel_arguments = (
            ('tegraid', '21.1.2.0.0'),
            ('ddr_die', '4096M@2048M'),
            ('section', '512M'),
            ('memtype', '0'),
            ('vpr_resize', ''),
            ('usb_port_owner_info', '0'),
            ('lane_owner_info', '0'),
            ('emc_max_dvfs', '0'),
            ('touch_id', '0@63'),
            ('video', 'tegrafb'),
            ('no_console_suspend', '1'),
            ('debug_uartport', 'lsport,4'),
            ('earlyprintk', 'uart8250-32bit,0x70006000'),
            ('maxcpus', '4'),
            ('usbcore.old_scheme_first', '1'),
            ('lp0_vec', '0x1000@0xff780000'),
            ('core_edp_mv', '1075'),
            ('core_edp_ma', '4000'),
            ('gpt', ''),
            ('tegra_fbmem', '0x800000@0x92ca9000'),
            ('earlycon', 'uart8250,mmio32,0x70006000'),
            ('sdhci_tegra.en_boot_part_access', '1'),
            ('rw', ''),
            ('fbcon', 'map:0'),
            ('net.ifnames', '0'),
            ('booted-via-pxe', 'true'),
            ('ip', '::::::dhcp'),
            ('console', 'ttyS0,115200'),
            )
        self._mac_address = _MACAddress(mac)
        self._local_ip = local_ip

    def apply(self, tftp_root: TFTPRoot, kernel_arguments: LinuxKernelArguments):
        tftp_root.set_for(self._local_ip)
        pxelinux_config = _mac_to_pxelinux_config(self._mac_address)
        final_kernel_arguments = kernel_arguments.with_arguments(*self._kernel_arguments)
        pxelinux_config_template = _get_jetson_pxelinux_template()
        with tftp_root.created_file(pxelinux_config) as wd:
            wd.write(pxelinux_config_template)
            wd.write(b'      APPEND ' + final_kernel_arguments.as_line().encode('utf-8') + b'\n')


def _mac_to_pxelinux_config(mac_address: '_MACAddress') -> str:
    # See: https://wiki.syslinux.org/wiki/index.php?title=PXELINUX
    formatted_mac = mac_address.formatted('%02x-%02x-%02x-%02x-%02x-%02x')
    return f'pxelinux.cfg/01-{formatted_mac}'


class _MACAddress:

    def __init__(self, value: str):
        match = re.compile(_mac_address_re).match(value.lower())
        if match is None or len(match.groups()) != 6:
            raise RuntimeError(
                f"MAC address should be in the xx:yy:zz:kk:ll:mm format while received {value!r}")
        self._mac = tuple(int(raw_byte, base=16) for raw_byte in match.groups())

    def formatted(self, template: str) -> str:
        return template % self._mac

    def __repr__(self):
        mac_text = ':'.join(f'{byte:02x}' for byte in self._mac)
        return f'<{mac_text}>'


_mac_address_re = (
    r'(?i)'
    r'^'
    r'([0-9a-f]{2})[-:]?'
    r'([0-9a-f]{2})[-:]?'
    r'([0-9a-f]{2})[-:]?'
    r'([0-9a-f]{2})[-:]?'
    r'([0-9a-f]{2})[-:]?'
    r'([0-9a-f]{2})[-:]?'
    r'$'
    )


def _get_jetson_pxelinux_template() -> bytes:
    return Path(__file__).with_name('jetson_nano_pxe_template').read_bytes()
