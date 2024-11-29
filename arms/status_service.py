# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Mapping


class MachinesStatus(ThreadingHTTPServer):

    request_queue_size = 128

    def __init__(self, listen_host: str, listen_port: int, status_dir: '_StatusDir'):
        super().__init__(
            (listen_host, listen_port),
            self._requests_handlers_factory)
        self._status_dir = status_dir

    def _requests_handlers_factory(self, *args):
        return _HTTPRequestsHandler(*args, status_dir=self._status_dir)


class _HTTPRequestsHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, status_dir: '_StatusDir'):
        self._status_dir = status_dir
        super().__init__(*args)

    def do_GET(self):
        logging.info("Received GET request from %s:%s to %s", *self.client_address, self.path)
        running_machines = self._status_dir.get_running()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        result_text = "NAME           STATUS    SUCCESSES FAILURES  UPTIME\n\n"
        for machine_name in sorted(running_machines.keys()):
            machine_status = running_machines[machine_name]
            result_text += (
                f"{machine_name:<15}"
                f"{machine_status['Status']:<10}"
                f"{machine_status.get('Successes', '-'):<10}"
                f"{machine_status.get('Failures', '-'):<10}"
                f"{machine_status.get('Uptime', '-'):<10}\n"
                )
        self.wfile.write(result_text.encode())


class _StatusDir:

    def __init__(self, path: Path):
        self._path = path

    def get_running(self) -> Mapping[str, Mapping[str, str]]:
        result = {}
        for socket_path in self._path.glob("*.sock"):
            _logger.info("%s: Found %s", self, socket_path)
            name = socket_path.stem
            try:
                opened_socket = _connected_unix_socket(str(socket_path), socket_timeout=5)
            except FileNotFoundError:
                _logger.info("%s: %s is removed while querying attempt", self, socket_path)
                continue
            except ConnectionError:
                _logger.warning("%s: %s is defunct", self, socket_path)
                result[name] = {'Status': 'DEFUNCT'}
                continue
            data = _recv_all(opened_socket)
            result[name] = _parse_status(data)
        return result

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._path}>'


def _recv_all(unix_socket: socket.socket) -> str:
    # Naive recv is used because of small amount of data and predictable unix socket behaviour
    return unix_socket.recv(1500).decode()


def _connected_unix_socket(raw_path: str, socket_timeout: float) -> socket.socket:
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.setblocking(False)
    client_socket.settimeout(socket_timeout)
    try:
        client_socket.connect(raw_path)
    except Exception:
        client_socket.close()
        raise
    return client_socket


def _parse_status(data: str) -> Mapping[str, str]:
    result = {}
    for line in data.splitlines():
        key, value = line.split(':')
        result[key.strip()] = value.strip()
    return result


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    status_dir = _StatusDir(Path('/tmp/status'))
    daemon = MachinesStatus(listen_host='0.0.0.0', listen_port=8000, status_dir=status_dir)
    try:
        daemon.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        logging.info("SIGINT received. Server closing ...")
    finally:
        # HTTPServer does not wait its socket closure
        # what may lead to AddressAlreadyInUse error.
        daemon.socket.close()
        logging.info("Server closed")
