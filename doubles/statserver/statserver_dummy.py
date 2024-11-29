# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from collections import namedtuple
from http.server import BaseHTTPRequestHandler
from queue import Empty
from queue import Queue
from socketserver import TCPServer

_HttpRequest = namedtuple('_HttpRequest', 'method path content')
_Result = namedtuple('_Result', 'request error')


class _EnqueueRequestHandler(BaseHTTPRequestHandler):

    def __process_request(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return _HttpRequest(self.command, self.path, None)
        content = self.rfile.read(content_length)
        content_str = content.decode(self.headers.get_content_charset('iso-8859-1'))
        if self.headers.get_content_type() == 'application/json':
            parsed_content = json.loads(content_str)
        else:
            parsed_content = content_str
        return _HttpRequest(self.command, self.path, parsed_content)

    def __handle_request(self):
        parsed_request = None
        error = None
        try:
            parsed_request = self.__process_request()
        except Exception as e:
            error = f"{e.__class__.__name__}: {e}"
            self.send_response(400)
        else:
            self.send_response(200)
        self.end_headers()
        self.server.result_queue.put(_Result(parsed_request, error))

    def log_message(self, format, *args):
        _logger.info(format, *args)

    do_GET = __handle_request
    do_POST = __handle_request


class _NoRequestError(Exception):
    pass


class StatisticsServer(TCPServer):

    def __init__(self, server_address):
        self.result_queue = Queue()
        super().__init__(server_address, _EnqueueRequestHandler, bind_and_activate=True)

    def handle_request_with_timeout(self, timeout_sec=None):
        self.socket.settimeout(timeout_sec)
        self.handle_request()
        try:
            result = self.result_queue.get_nowait()
        except Empty:
            raise _NoRequestError(f"No request received in {timeout_sec} seconds")
        if result.error is not None:
            raise RuntimeError(f"Failed to handle request: {result.error}")
        return result.request

    def ensure_no_requests_received(self, silence_period_sec):
        try:
            request = self.handle_request_with_timeout(timeout_sec=silence_period_sec)
        except _NoRequestError:
            pass
        else:
            raise RuntimeError(
                f"Request received during silence period ({silence_period_sec} seconds): "
                f"{request}")


_logger = logging.getLogger()
