# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from io import StringIO
from pathlib import Path
from typing import Collection
from typing import Sequence
from typing import Tuple
from urllib.parse import urlencode
from urllib.parse import urlparse
from xml.sax.saxutils import XMLGenerator

from infrastructure.json_to_xml import json_to_xml

_logger = logging.getLogger(__name__)


class HTTPMethod(Enum):
    GET = 'GET'
    POST = 'POST'
    _UNSUPPORTED = '_UNSUPPORTED '

    @classmethod
    def _missing_(cls, value):
        return cls._UNSUPPORTED


class _RequestHandler(metaclass=ABCMeta):

    @abstractmethod
    def handle(self, request: BaseHTTPRequestHandler):
        pass


class _MethodNotAllowed(Exception):
    pass


class _PathMismatch(Exception):
    pass


class MethodHandler(_RequestHandler):
    _path: str
    _method: HTTPMethod

    @abstractmethod
    def _handle(self, request: BaseHTTPRequestHandler):
        pass

    def handle(self, request: BaseHTTPRequestHandler):
        path = urlparse(request.path).path
        if not self._path == path:
            raise _PathMismatch()
        method = HTTPMethod(request.command)
        if method != self._method:
            raise _MethodNotAllowed()
        self._handle(request)

    @classmethod
    def url(cls, *query: Tuple[str, str]):
        return cls._path + f'?{urlencode(query)}' if query else cls._path


class StaticFilesHandler(_RequestHandler):

    def __init__(self, app_root: Path, relative_paths: Collection[str]):
        self._content_mapping = {
            relative_path: Path(app_root, relative_path.lstrip('/')).read_bytes()
            for relative_path in relative_paths
            }

    def handle(self, request):
        path = urlparse(request.path).path
        if path not in self._content_mapping:
            raise _PathMismatch()
        method = HTTPMethod(request.command)
        if method != HTTPMethod.GET:
            raise _MethodNotAllowed()
        file_type = Path(path).suffix[1:]
        request.send_response(HTTPStatus.OK.value)
        request.send_header('Content-type', f'text/{file_type}')
        request.end_headers()
        request.wfile.write(self._content_mapping[path])


class XSLTemplateHandler(MethodHandler):

    def __init__(self, template_location: str):
        self._template_href = '"' + template_location + '"'

    def _send_template_data(self, request, data):
        buffer = StringIO()
        xml = XMLGenerator(buffer, encoding="utf-8")
        xml.startDocument()
        xml.processingInstruction('xml-stylesheet', f'type="text/xsl" href={self._template_href}')
        content = buffer.getvalue().encode('utf8') + json_to_xml(data).encode('utf8')
        request.send_response(HTTPStatus.OK.value)
        request.send_header('Content-type', 'text/xml')
        request.end_headers()
        request.wfile.write(content)


class App(BaseHTTPRequestHandler):
    timeout = 10

    def __init__(self, request, client_address, server, handlers: Sequence[_RequestHandler]):
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

    def log_request(self, code='-', size='-'):
        pass

    def log_message(self, format, *args):
        _logger.debug(format, *args)
