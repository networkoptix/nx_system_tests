# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import tempfile
import unittest
from pathlib import Path

from arms.boot_loader.jetson_nano import JetsonNanoTFTPBootloader
from arms.boot_loader.orin_nano import OrinNanoTFTPBootloader
from arms.boot_loader.raspberry import RaspberryTFTPBootloader
from arms.machines.machine import ISCSIExt4Root
from arms.power_control_interface import PowerControlInterface
from arms.remote_control import ARMRemoteControl
from arms.tftp_roots_storage import LocalTFTPRoot
from arms.tftp_server_interface import TFTPServerControl


class _StubPowerControl(PowerControlInterface):

    async def power_on(self):
        raise RuntimeError(f"power_on on {self} should not have been called")

    async def power_off(self):
        raise RuntimeError(f"power_off on {self} should not have been called")


class _StubRemoteControl(ARMRemoteControl):

    async def shutdown(self):
        raise RuntimeError(f"shutdown on {self} should not have been called")


class _StubTFTPServerControl(TFTPServerControl):

    def set_tftp_root_for(self, ip_address: str, tftp_root: Path):
        pass


class TestConfigureTFTPServer(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())

    def test_configure_tftp_jetson(self):
        machine_name = 'irrelevant'
        server_ip = '192.168.0.1'
        server_port = 3260
        mac = "11:22:33:44:55:ab"
        tftp_boot_loader = JetsonNanoTFTPBootloader(local_ip="192.168.0.2", mac=mac)
        fs_root = ISCSIExt4Root(server_ip, server_port, machine_name)
        tftp_root = LocalTFTPRoot(_StubTFTPServerControl(), self._tmp_dir)
        tftp_boot_loader.apply(tftp_root, fs_root.get_arguments())
        expected_config = self._tmp_dir / _mac_to_pxelinux_config_file(mac)
        pxelinux_config_text = expected_config.read_text('utf-8')
        self.assertIn('ip=::::::dhcp', pxelinux_config_text)
        self.assertIn("root=LABEL=rootfs", pxelinux_config_text)
        self.assertRegex(pxelinux_config_text, f' ISCSI_INITIATOR=.*:{machine_name}')
        self.assertIn(f'ISCSI_TARGET_IP={server_ip}', pxelinux_config_text)
        self.assertIn(f'ISCSI_TARGET_PORT={server_port}', pxelinux_config_text)
        self.assertRegex(pxelinux_config_text, f' ISCSI_TARGET_NAME=.*:{machine_name}')
        self.assertIn('rootfstype=ext4', pxelinux_config_text)

    def test_configure_tftp_raspberry(self):
        machine_name = 'irrelevant'
        server_ip = '192.168.0.1'
        server_port = 3260
        serial = "aabbccdd"
        tftp_boot_loader = RaspberryTFTPBootloader(local_ip="192.168.0.2", serial=serial)
        fs_root = ISCSIExt4Root(server_ip, server_port, machine_name)
        tftp_root = LocalTFTPRoot(_StubTFTPServerControl(), self._tmp_dir)
        tftp_boot_loader.apply(tftp_root, fs_root.get_arguments())
        expected_config = self._tmp_dir / serial / 'cmdline.txt'
        kernel_arguments = expected_config.read_text('utf-8')
        self.assertIn(f'ip=::::{serial}:eth0:dhcp', kernel_arguments)
        self.assertIn("root=LABEL=rootfs", kernel_arguments)
        self.assertRegex(kernel_arguments, f' ISCSI_INITIATOR=.*:{machine_name}')
        self.assertIn(f'ISCSI_TARGET_IP={server_ip}', kernel_arguments)
        self.assertIn(f'ISCSI_TARGET_PORT={server_port}', kernel_arguments)
        self.assertRegex(kernel_arguments, f' ISCSI_TARGET_NAME=.*:{machine_name}')
        self.assertIn('rootfstype=ext4', kernel_arguments)

    def test_configure_tftp_orin(self):
        machine_name = 'irrelevant'
        server_ip = '192.168.0.1'
        server_port = 3260
        mac = "11:22:33:44:55:ab"
        tftp_boot_loader = OrinNanoTFTPBootloader(local_ip="192.168.0.2", mac=mac)
        fs_root = ISCSIExt4Root(server_ip, server_port, machine_name)
        tftp_root = LocalTFTPRoot(_StubTFTPServerControl(), self._tmp_dir)
        tftp_boot_loader.apply(tftp_root, fs_root.get_arguments())
        main_grub_config = self._tmp_dir / 'grub' / 'grub.cfg'
        device_grub_config = self._tmp_dir / 'grub' / f'grub.cfg-{mac}'
        main_grub_config_text = main_grub_config.read_text('ascii')
        self.assertIn('${net_default_mac}', main_grub_config_text)
        grub_config_text = device_grub_config.read_text('ascii')
        self.assertIn('ip=:::::eth0:dhcp', grub_config_text)
        self.assertIn("root=LABEL=rootfs", grub_config_text)
        self.assertRegex(grub_config_text, f' ISCSI_INITIATOR=.*:{machine_name}')
        self.assertIn(f'ISCSI_TARGET_IP={server_ip}', grub_config_text)
        self.assertIn(f'ISCSI_TARGET_PORT={server_port}', grub_config_text)
        self.assertRegex(grub_config_text, f' ISCSI_TARGET_NAME=.*:{machine_name}')
        self.assertIn('rootfstype=ext4', grub_config_text)


def _mac_to_pxelinux_config_file(mac: str) -> str:
    # See: https://wiki.syslinux.org/wiki/index.php?title=PXELINUX
    formatted_mac = mac.replace(':', '-').lower()
    return f'pxelinux.cfg/01-{formatted_mac}'
