# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging.handlers
from datetime import datetime
from datetime import timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from pathlib import Path
from typing import Any
from typing import Optional
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse

from infrastructure.ft_view import _db
from infrastructure.ft_view._enrichment import enrich
from infrastructure.ft_view.web_ui._batches_blueprint import queued_progress


def main():
    _db.execute(Path(__file__).with_name('job_status_update.sql').read_text())
    _db.execute(Path(__file__).with_name('batches_api.sql').read_text())
    server = HTTPServer(('', 8094), _Handler)
    _logger.info("Serving at :%d", server.server_port)
    server.serve_forever()


class _Handler(BaseHTTPRequestHandler):
    # Without timeout on incoming connections any client can hang
    # current service, because HTTP server has a single thread.
    # 10 seconds is more than enough for a client to finish a request.
    timeout = 10
    _input: Any

    # noinspection PyPep8Naming
    def do_POST(self):
        # Always read out data.
        content_length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(content_length)
        try:
            self._input = json.loads(raw)
        except ValueError as e:
            self.send_error(HTTPStatus.BAD_REQUEST, str(e))
            return
        path = urlparse(self.path).path.rstrip('/')
        _logger.debug("%s: %s", self.command, self.path)
        if path == '/batches/start':
            progress = queued_progress(self._input.get('priority'))
            batch_data = {
                **self._input['args']['cmdline'],
                'created_at': datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                }
            enrich(batch_data)
            _db.perform(
                'pg_temp.start_batch',
                json.dumps(self._input['args']['cmdline']),
                json.dumps(batch_data),
                progress,
                json.dumps(self._input['tests']),
                )
            self._send_post_response('/batches/get?' + urlencode(self._input['args']['cmdline']))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    # noinspection PyPep8Naming
    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/')
        _logger.debug("%s: %s", self.command, self.path)
        if path == '/batches/get':
            query = dict(parse_qsl(urlparse(self.path).query))
            row = _db.select_one(
                'SELECT data '
                'FROM batch '
                'WHERE cmdline = %(cmdline)s '
                ';', {
                    'cmdline': json.dumps(query),
                    })
            if row is not None:
                # TODO: Change this API later; mind compatibility
                out_counters = {
                    'passed_count': 0,
                    'failed_count': 0,
                    'pending_count': 0,
                    }
                for key, value in row['data'].items():
                    if key.startswith('count.') and value is not None:
                        if key == 'count.passed' or key == 'count.skipped':
                            out_key = 'passed_count'
                        elif key == 'count.failed':
                            out_key = 'failed_count'
                        else:  # 'pending', 'running' and obsolete ones.
                            out_key = 'pending_count'
                        try:
                            out_counters[out_key] += int(value)
                        except ValueError:
                            _logger.error("Cannot convert %s: %r", key, value)
                self._send_json(out_counters)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _send_json(self, data):
        data = json.dumps(data).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_post_response(self, location: Optional[str]):
        self.send_response(HTTPStatus.NO_CONTENT)
        if location is not None:
            self.send_header('Location', location)
        self.end_headers()


_logger = logging.getLogger()

if __name__ == '__main__':
    log_dir = Path('~/.cache/ft_view_logs').expanduser()
    log_dir.mkdir(exist_ok=True, parents=False)
    log_file = log_dir / Path(__file__).with_suffix('.log').name
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=200 * 1024**2, backupCount=6)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(stream_handler)
    logging.getLogger().setLevel(logging.DEBUG)
    main()
