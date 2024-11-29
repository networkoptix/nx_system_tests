# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import html
import logging
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Sequence
from enum import Enum
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import XMLGenerator

from infrastructure.json_to_xml import json_to_xml
from long_tests.control_panel._tasks import get_tasks_log


def make_app():
    return partial(_App, handlers=[
        _TasksLogHandler('/task_list'),
        _StaticFileHandler('/templates/task_list.xsl'),
        _StaticFileHandler('/templates/task_table.css'),
        ])


class _HTTPMethod(Enum):
    GET = 'GET'
    POST = 'POST'
    _UNSUPPORTED = '_UNSUPPORTED '

    @classmethod
    def _missing_(cls, value):
        return cls._UNSUPPORTED


class _App(BaseHTTPRequestHandler):
    timeout = 10  # There is an overridden attribute from the base class

    def __init__(self, request, client_address, server, handlers: Sequence['_RequestHandler']):
        self._handlers = handlers
        super().__init__(request, client_address, server)

    def __handle_request(self):
        path = urlparse(self.path).path
        method_not_allowed = False
        for handler in self._handlers:
            try:
                handler.handle(self)
            except _MethodNotAllowed:
                method_not_allowed = True
                continue
            except _PathMismatch:
                continue
            except Exception as e:
                _logger.warning("Exception during %r request handling", path, exc_info=e)
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR.value)
                self.end_headers()
                return
            else:
                return
        if method_not_allowed:
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED.value)
        else:
            self.send_response(HTTPStatus.NOT_FOUND.value)
        self.end_headers()

    do_GET = __handle_request
    do_POST = __handle_request

    def log_message(self, format, *args):
        _logger.debug(format, *args)


class _RequestHandler(metaclass=ABCMeta):

    @abstractmethod
    def handle(self, request: BaseHTTPRequestHandler):
        pass


class _StaticFileHandler(_RequestHandler):

    def __init__(self, relative_path: str):
        self._content = Path(__file__, f'../{relative_path}').resolve().read_bytes()
        self._path = relative_path

    def handle(self, request: BaseHTTPRequestHandler):
        path = urlparse(request.path).path
        if self._path != path:
            raise _PathMismatch()
        method = _HTTPMethod(request.command)
        if method != _HTTPMethod.GET:
            raise _MethodNotAllowed()
        file_type = Path(self._path).suffix[1:]
        request.send_response(HTTPStatus.OK.value)
        request.send_header('Content-type', f'text/{file_type}')
        request.end_headers()
        request.wfile.write(self._content)


class _TasksLogHandler(_RequestHandler):

    def __init__(self, relative_path: str):
        self._path = relative_path

    def handle(self, request: BaseHTTPRequestHandler):
        path = urlparse(request.path).path
        if self._path != path:
            raise _PathMismatch()
        buffer = StringIO()
        data = get_tasks_log()
        for item in data:
            item['error'] = html.escape(item['error'])
        xml = XMLGenerator(buffer)
        xml.startDocument()
        xml.processingInstruction('xml-stylesheet', 'type="text/xsl" href="templates/task_list.xsl"')
        request.send_response(HTTPStatus.OK.value)
        request.send_header('Content-type', 'text/xml')
        request.end_headers()
        request.wfile.write(buffer.getvalue().encode('utf8') + json_to_xml(data).encode('utf8'))


class _MethodNotAllowed(Exception):
    pass


class _PathMismatch(Exception):
    pass


_logger = logging.getLogger(__name__)
