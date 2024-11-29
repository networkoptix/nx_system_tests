# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import json
import logging
import ssl
import urllib.parse
from abc import ABCMeta
from abc import abstractmethod
from contextlib import closing
from http.client import HTTPResponse as BaseHttpResponse
from http.client import HTTPSConnection as BaseHttpsConnection
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Union
from urllib.parse import urljoin

from mediaserver_api import CannotHandleRequest


class HttpResponse:

    def __init__(self, response: BaseHttpResponse, request_method: str, url: str):
        self.status_code: int = response.status
        self.reason: str = response.reason
        self.headers = response.headers
        self.request_method = request_method
        self.url = url
        self.content = response.read()
        try:
            self.json = json.loads(self.content.decode('utf-8'))
        except ValueError:
            self.json = None


class _HttpRequest:

    def __init__(
            self,
            method: str,
            url: str,
            content: Optional[Union[Iterable[Mapping[str, Any]], Mapping[str, Any], bytes]] = None,
            headers: Optional[Mapping[str, str]] = None,
            ):
        self.method = method
        self.url = url
        if headers is None:
            headers = {}
        if content is not None:
            if isinstance(content, bytes):
                headers = {**{'Content-Type': 'application/octet-stream', **headers}}
            elif isinstance(content, (Iterable, Mapping)):
                content = json.dumps(content)
                headers = {**{'Content-Type': 'application/json', **headers}}
            else:
                raise RuntimeError(f"Unsupported content type: {content.__class__.__name__}")
        else:
            headers = {**{'Content-Length': 0, **headers}}  # To avoid adding Transfer-Encoding
        self.headers = headers
        self.content = content


class _AuthHandler(metaclass=ABCMeta):

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @abstractmethod
    def authorize_request(self, request: _HttpRequest):
        pass

    @abstractmethod
    def make_authorization_header(self) -> str:
        pass

    def handle_failed_request(self, request: _HttpRequest, response: HttpResponse):
        raise CannotHandleRequest("Handling not supported")

    def with_credentials(self, username: str, password: str):
        return self.__class__(username, password)

    @abstractmethod
    def subsume_from_master(self, master: '_AuthHandler'):
        pass


class HttpBasicAuthHandler(_AuthHandler):

    def authorize_request(self, request):
        request.headers['Authorization'] = self.make_authorization_header()

    def make_authorization_header(self) -> str:
        credentials = f'{self.username}:{self.password}'
        basic = base64.b64encode(credentials.encode()).decode()
        return f'Basic {basic}'

    def subsume_from_master(self, master: _AuthHandler):
        # It is just a coincidence that all available authentication types have
        # username and password.
        self.username = master.username
        self.password = master.password


class _HttpsConnection(BaseHttpsConnection):

    def __init__(
            self,
            host: str,
            port: int,
            ssl_context: ssl.SSLContext,
            auth_handler: Optional['_AuthHandler'] = None,
            timeout: Optional[float] = None,
            ):
        super().__init__(host, port, timeout=timeout, context=ssl_context)
        self._auth_handler = auth_handler

    def send_request(self, request: _HttpRequest) -> HttpResponse:
        if self._auth_handler is not None:
            self._auth_handler.authorize_request(request)
        super().request(request.method, request.url, request.content, request.headers)
        response = HttpResponse(super().getresponse(), request.method, request.url)
        if response.status_code in (401, 403):
            if self._auth_handler is None:
                return response
            try:
                self._auth_handler.handle_failed_request(request, response)
            except CannotHandleRequest:
                return response
            super().request(request.method, request.url, request.content, request.headers)
            response = HttpResponse(super().getresponse(), request.method, request.url)
        return response


def http_request(
        method: str,
        url: str,
        content: Optional[Union[Iterable[Mapping[str, Any]], Mapping[str, Any], bytes]] = None,
        *,
        headers: Optional[Mapping[str, Any]] = None,
        timeout: float = 30,
        auth_handler: Optional['_AuthHandler'] = None,
        ca_cert: Optional[str] = None,
        allow_redirects: bool = False,
        redirect_depth: Optional[int] = 10,
        ) -> 'HttpResponse':
    if headers is None:
        headers = {}
    headers = {'Connection': 'Keep-Alive', **headers}
    request = _HttpRequest(method, url, content, headers)
    parsed_url = urllib.parse.urlparse(url)
    ssl_context = ssl.create_default_context()
    if ca_cert is not None:
        ssl_context.load_verify_locations(ca_cert)
    with closing(
            _HttpsConnection(
                parsed_url.hostname,
                parsed_url.port,
                ssl_context,
                auth_handler,
                timeout=timeout,
                )) as connection:  # type: _HttpsConnection
        try:
            response = connection.send_request(request)
        except (ConnectionError, ssl.SSLEOFError, ssl.SSLZeroReturnError):
            raise _HttpConnectionError()
        except TimeoutError:
            raise _HttpReadTimeout()
    _logger.debug(
        "HTTP response: [%s] %s\n%s", response.status_code, response.reason, response.content)
    location_header = response.headers.get('location')
    if location_header is None:
        return response
    # Handle redirect.
    if not allow_redirects:
        raise _RedirectNotAllowed()
    if redirect_depth == 0:
        raise _RedirectDepthExceeded()
    if location_header.startswith('/'):
        next_url = urljoin(url, location_header)
    else:
        next_url = location_header
    return http_request(
        method=method,
        url=next_url,
        headers=headers,
        content=content,
        auth_handler=auth_handler,
        ca_cert=ca_cert,
        timeout=timeout,
        allow_redirects=True,
        redirect_depth=redirect_depth - 1,
        )


class _HttpConnectionError(Exception):
    pass


class _HttpReadTimeout(Exception):
    pass


class _RedirectNotAllowed(Exception):
    pass


class _RedirectDepthExceeded(Exception):
    pass


_logger = logging.getLogger(__name__)
