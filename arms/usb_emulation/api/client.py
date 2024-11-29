# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import socket

from usb_emulation.api.protocol import Request
from usb_emulation.api.protocol import Response


class UsbIpServerError(Exception):
    pass


class UsbIpServerClient:

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def add_disk(self, machine_name: str, size_mb: int):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self._host, self._port))
        try:
            file = sock.makefile('rw')
            file.write(str(Request.add(machine_name, size_mb)) + '\n')
            file.flush()
            response_raw = file.readline().rstrip('\n')
            result = Response.unpack(response_raw)
            if result.status == 0:
                return
            raise UsbIpServerError(result.message)
        finally:
            sock.close()

    def delete_disk(self, machine_name: str):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self._host, self._port))
        try:
            file = sock.makefile('rw')
            file.write(Request.delete(machine_name) + '\n')
            file.flush()
            result = Response.unpack(file.readline().rstrip('\n'))
            if result.status == 0:
                return
            raise UsbIpServerError(result.message)
        finally:
            sock.close()
