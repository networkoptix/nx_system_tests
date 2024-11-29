# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import wsgiref.simple_server
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from socket import AF_INET
from socket import SOCK_DGRAM
from socket import socket
from threading import Thread
from typing import Mapping
from typing import Union

from ca import default_ca
from doubles.licensing._licensing_server import LicenseServer
from doubles.licensing.local_license_server._app import app
from doubles.licensing.local_license_server._license import activate_license
from doubles.licensing.local_license_server._license import deactivate_license
from doubles.licensing.local_license_server._license import disable_license
from doubles.licensing.local_license_server._license import generate_license

_logger = logging.getLogger(__name__)


class LocalLicenseServer(LicenseServer):

    def __init__(self):
        with socket(AF_INET, SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 53))
            [self._ip_address, _] = s.getsockname()  # "Main" host address

    @contextmanager
    def serving(self):
        with ExitStack() as stack:
            server = stack.enter_context(_wsgi_server())
            hostnames = ['127.0.0.1', self._ip_address]
            server.socket = default_ca().wrap_server_socket(server.socket, hostnames)
            thread = Thread(target=server.serve_forever, name='Thread-LocalLicenseServer', daemon=True)
            thread.start()
            [_, self._port] = server.socket.getsockname()
            _logger.info("Started local license server %s", self.url())
            try:
                yield self
            finally:
                self._port = None

    def url(self):
        if self._port is None:
            raise RuntimeError("Port is dynamic, bind socket first")
        return f'https://{self._ip_address}:{self._port}'

    def generate(self, license_data: Mapping[str, Union[str, float]]) -> str:
        [key, _serial] = generate_license(license_data)
        return key

    def activate(self, license_key: str, hardware_id: str) -> str:
        return activate_license(license_key, 'manual', {'hwid[]': [hardware_id]})

    def deactivate(self, license_key: str):
        deactivate_license(license_key)

    def disable(self, license_key: str):
        disable_license(license_key)

    def info(self, license_key: str):
        raise NotImplementedError()


@contextmanager
def _wsgi_server() -> AbstractContextManager[wsgiref.simple_server.WSGIServer]:
    host = '0.0.0.0'
    server = wsgiref.simple_server.make_server(
        host=host,
        port=0,
        app=app,
        server_class=wsgiref.simple_server.WSGIServer,
        )
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
