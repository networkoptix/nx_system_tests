# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from argparse import ArgumentParser
from pathlib import Path

from arms.ptftp._endpoints_registry import FileEndpointsRegistry
from arms.ptftp._server import TFTPServer
from arms.ptftp._server import bind_udp_socket

_logger = logging.getLogger(__name__)


def _socket_to_tuple(raw: str) -> tuple[str, int]:
    ip, _sep, port = raw.partition(":")
    if port:
        return ip, int(port)
    return ip, 69


def _existing_directory(raw: str) -> Path:
    path = Path(raw)
    if not path.exists():
        raise FileNotFoundError(f"{path} configuration directory does not exist")
    return path


def main():
    parser = ArgumentParser(description='TFTP server')
    parser.add_argument(
        '--config-dir', '-c',
        dest='config_dir',
        required=True,
        type=_existing_directory,
        help='Configuration directory',
        )
    parser.add_argument(
        '--listen-on', '-l',
        dest='listen_socket',
        default=('0.0.0.0', 69),
        type=_socket_to_tuple,
        required=False,
        help='IP:port to listen on',
        )
    parser.add_argument(
        '--debug-level', '-d',
        dest='debug_level',
        default=logging.INFO,
        type=int,
        choices=[logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL],
        required=False,
        help='Debug level',
        )
    args = parser.parse_args()
    logging.basicConfig(
        level=args.debug_level, format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    endpoint_registry = FileEndpointsRegistry(args.config_dir)
    listen_ip, listen_port = args.listen_socket
    server_socket = bind_udp_socket(listen_ip, listen_port)
    tftp_server = TFTPServer(server_socket, endpoint_registry)
    with server_socket:
        _logger.info("Start listening TFTP server on %s:%s", listen_ip, listen_port)
        try:
            tftp_server.serve_forever(16)
        except KeyboardInterrupt:
            _logger.info("Closing server ...")
    tftp_server.wait_requests_done()
    _logger.info("Server closed")
    _logger.info("Sessions closed, daemon exited")


if __name__ == '__main__':
    main()
