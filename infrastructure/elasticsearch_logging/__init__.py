# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""
Main principles.

- Elastic shouldn't be used in tests explicitly.
- Any problems with Elastic or with sending logs shouldn't influence the tests.
- Do not use logging during log processing.
"""
import json
import logging
import netrc
import queue
import sys
import time
from base64 import b64encode
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from threading import Thread
from typing import Any
from typing import Mapping
from typing import MutableMapping
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

from infrastructure.elasticsearch_logging._buffer import Buffer

_logger = logging.getLogger(__name__)


class ElasticsearchHandler(logging.Handler):

    def __init__(self, instance: 'Elasticsearch', index: str, additional_data):
        super().__init__()
        self._index = index
        self._additional_data = additional_data
        self._instance = instance
        self._queue = queue.Queue(maxsize=100000)
        self._max_buffer_length = 1000
        self._logs_send_interval_seconds = 10
        self._thread = Thread(
            # If an exception happens during the loop, just let it exit.
            # The traceback will be printed by Python to stderr.
            # Do not do anything with logging, as it may cause deadlock
            # with the lock object used by Python's logging system.
            target=self._sending_loop,
            name=f'Thread-{self.__class__.__name__}',
            daemon=True,
            )
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        if not hasattr(record, 'message'):
            # The message field may be missing if the root logger is not
            # configured properly or if the log message has been built with
            # an error (not enough parameters for example).
            sys.stderr.write(
                f"LogRecord '{record.msg!r}' does not have a field 'message'\n")
            return
        self._queue.put_nowait({
            'message': record.message,
            'template': record.msg,
            'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec='microseconds'),
            'thread': {'name': record.threadName, 'id': record.thread},
            'process': {'name': record.processName, 'id': record.process},
            'level': {'name': record.levelname, 'level': record.levelno},
            'logger': record.name,
            'location': {'pathname': record.pathname, 'line': record.lineno},
            'exc': (
                # Normal logging, e.g. Logger.info()
                {} if record.exc_info is None else
                # Logger.exception() without an active exception.
                {} if record.exc_info == (None, None, None) else
                # Normal Logger.exception(), i.e. with an active exception.
                {
                    'type': record.exc_info[0].__name__,
                    'value': repr(record.exc_info[1]),
                    }),
            'args': record.args if isinstance(record.args, dict) else {},
            **self._additional_data,
            })

    def close(self) -> None:
        self._queue.put_nowait(self._stop_marker)
        # It either already exited because of an exception or will exit soon
        # when consuming the stop marker.
        self._thread.join()
        super().close()

    def _sending_loop(self):
        while True:
            try:
                event = self._queue.get(timeout=self._logs_send_interval_seconds)
            except queue.Empty:
                self._instance.flush()
                continue
            if event is self._stop_marker:
                break
            self._instance.send(self._index, event)
        self._instance.flush()

    _stop_marker = object()


class Elasticsearch:

    def __init__(self, url: str):
        self._url = url.rstrip('/')
        self._buffers: MutableMapping[str, Buffer] = {}
        self._date = datetime.utcnow().date()  # For consistent index names.

    def send_flush(self, target: str, item):
        self.send(target, item)
        self.flush()

    def send(self, target_pattern: str, item):
        target = self._format_index_name(target_pattern)
        if target not in self._buffers:
            self._buffers[target] = Buffer(100)
        self._buffers[target].append(self._format(item))
        if self._buffers[target].too_much():
            self._flush(target)

    def flush(self):
        for target in self._buffers:
            self._flush(target)

    def _flush(self, target: str):
        while True:
            blob = self._buffers[target].read_out()
            if not blob:
                break
            self._bulk_insert(target, blob)

    def _bulk_insert(self, target: str, items: bytes) -> None:
        request = self._build_request(target, items)
        delay: int = 1
        attempts_left: int = 5
        while True:
            try:
                self._perform_request(request)
                break
            except (URLError, ConnectionError, TimeoutError):
                if attempts_left == 0:
                    raise
                attempts_left -= 1
                time.sleep(delay)
                delay *= 2

    def search(self, target: str, query: str) -> Mapping[str, Any]:
        """Search target (comma-separated indices, wildcards supported)."""
        request = Request(
            f'{self._url}/{target}/_search',
            data=query.encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': self._auth_header(),
                })
        return self._perform_request(request)

    @staticmethod
    def _perform_request(request):
        response = urlopen(request, timeout=10)
        outcome = json.load(response)
        if outcome.get('errors'):
            sys.stderr.write('--- Elasticsearch error ---\n')
            for item in outcome['items']:
                if 'index' in item and item['index']['status'] != 201:
                    sys.stderr.write(json.dumps(item['index']['error']) + '\n')
        return outcome

    @staticmethod
    def _format(item):
        d = json.dumps(item, default=repr)
        return b'{"index": {}}\n' + d.encode('utf-8') + b'\n'

    def _build_request(self, target: str, items):
        return Request(
            f'{self._url}/{target}/_bulk',
            data=items,
            headers={
                'Content-Type': 'application/json',
                'Authorization': self._auth_header(),
                })

    @lru_cache()
    def _auth_header(self):
        netrc_db = netrc.netrc(Path('~/.config/.secrets/elasticsearch.netrc').expanduser())
        host = urlparse(self._url).hostname
        [username, _, password] = netrc_db.authenticators(host)
        token = b64encode(f'{username}:{password}'.encode('ascii')).decode('ascii')
        auth_header = f'Basic {token}'
        return auth_header

    def _format_index_name(self, pattern: str) -> str:
        """Substitute date fields. 2-digit month and day for correct order."""
        return pattern.format(
            YYYY=self._date.strftime('%Y'),
            MM=self._date.strftime('%m'),
            DD=self._date.strftime('%d'),
            )


__all__ = [
    'Elasticsearch',
    'ElasticsearchHandler',
    ]
