# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
import subprocess
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from typing import Sequence

from infrastructure._logging import init_logging
from infrastructure._uri import get_process_uri

_logger = logging.getLogger()


def main():
    server = HTTPServer(('', 8060), _Handler)
    server.serve_forever()


class _Handler(BaseHTTPRequestHandler):
    timeout = 10

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        command = self.rfile.read(content_length)
        command = command.decode('ascii')
        _logger.info("Command: %s", command)
        command = shlex.split(command)
        if not _command_is_allowed(command):
            self.send_error(422, "Command is not allowed")
            return
        process = subprocess.run(command, check=False, capture_output=True)
        if process.returncode != 0:
            _logger.info(
                "Command %s failed with code %d: stdout=%s stderr=%s",
                command, process.returncode, process.stdout, process.stderr,
                )
            self.send_error(422, f"Exit code {process.returncode}")
            return
        self.send_response(200)
        self.send_header('Content-Length', str(len(process.stdout)))
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(process.stdout)

    def log_message(self, message, *args):
        _logger.debug(message, *args)


def _command_is_allowed(command: Sequence[str]) -> bool:
    allowed_commands = [
        ('systemctl', '--user'),
        ('journalctl', '--user'),
        ]
    return tuple(command[0:2]) in allowed_commands


if __name__ == '__main__':
    init_logging(get_process_uri())
    logging.basicConfig(level='DEBUG')
    main()
