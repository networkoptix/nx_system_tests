# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket
import threading

from usb_emulation.usb.usb_registry import UsbDeviceRegistry
from usb_emulation.usb_ip.usbip_session import UsbIpSession


class UsbIpServer:
    def __init__(
            self,
            usb_device_registry: UsbDeviceRegistry,
            host: str = '0.0.0.0',
            port: int = 3240,
            ):
        self._host = host
        self._port = port
        self._socket = None
        self.usb_device_registry = usb_device_registry

    def main(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._socket.bind((self._host, self._port))
        self._socket.listen(5)
        try:
            while True:
                [connection, _] = self._socket.accept()
                session = UsbIpSession(connection, self.usb_device_registry)
                threading.Thread(target=session.listen).start()
        finally:
            self._socket.close()
