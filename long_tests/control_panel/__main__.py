# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging.handlers
from http.server import HTTPServer
from pathlib import Path

from long_tests.control_panel._app import make_app


def main() -> int:
    logging.getLogger().setLevel(logging.DEBUG)
    log_file = 'control_panel.log'
    service_log_dir = Path('~/.cache/control_panel').expanduser()
    service_log_dir.mkdir(exist_ok=True, parents=True)
    log_file = service_log_dir / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=200 * 1024**2, backupCount=6)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(stream_handler)
    _logger = logging.getLogger(__name__)
    app = make_app()
    address, port = '0.0.0.0', 8060
    with HTTPServer((address, port), app) as server:
        _logger.info("Start listening HTTP server on %s:%s", address, port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            _logger.info("Closing server ...")
    return 0


if __name__ == '__main__':
    exit(main())
