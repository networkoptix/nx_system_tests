# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import json
import ssl
import urllib.parse
import urllib.request
from abc import ABCMeta
from abc import abstractmethod
from contextlib import closing
from http.client import HTTPResponse as BaseHttpResponse
from http.client import HTTPSConnection as BaseHttpsConnection
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Protocol
from typing import Union

from mediaserver_api._http_auth import calculate_digest

DEFAULT_HTTP_TIMEOUT = 30


def http_request(
        method: str,
        url: str,
        content: Optional[Union[Iterable[Mapping[str, Any]], Mapping[str, Any], bytes]] = None,
        *,
        headers: Optional[Mapping[str, Any]] = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
        auth_handler: Optional['AuthHandler'] = None,
        ca_cert: Optional[str] = None,
        ) -> '_HttpResponse':
    if timeout is None:
        raise RuntimeError("Timeout must not be None; otherwise a request may be endless")
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
            return connection.send_request(request)
        except (ConnectionError, ssl.SSLEOFError, ssl.SSLZeroReturnError):
            raise HttpConnectionError()
        except TimeoutError:
            raise HttpReadTimeout()


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


class _HttpResponse:

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


class _HttpsConnection(BaseHttpsConnection):

    def __init__(
            self,
            host: str,
            port: int,
            ssl_context: ssl.SSLContext,
            auth_handler: Optional['AuthHandler'] = None,
            timeout: Optional[float] = None,
            ):
        super().__init__(host, port, timeout=timeout, context=ssl_context)
        self._auth_handler = auth_handler

    def send_request(self, request: _HttpRequest) -> _HttpResponse:
        if self._auth_handler is not None:
            try:
                self._auth_handler.authorize_request(request)
            except _CannotAuthorizeRequest:
                pass
        super().request(request.method, request.url, request.content, request.headers)
        response = _HttpResponse(super().getresponse(), request.method, request.url)
        if response.status_code in (401, 403) and self._auth_handler is not None:
            try:
                self._auth_handler.handle_failed_request(request, response)
            except CannotHandleRequest:
                return response
            super().request(request.method, request.url, request.content, request.headers)
            response = _HttpResponse(super().getresponse(), request.method, request.url)
        return response


class AuthHandler(metaclass=ABCMeta):

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @abstractmethod
    def authorize_request(self, request: _HttpRequest):
        pass

    @abstractmethod
    def make_authorization_header(self) -> str:
        pass

    def handle_failed_request(self, request: _HttpRequest, response: _HttpResponse):
        raise CannotHandleRequest("Handling not supported")

    def with_credentials(self, username: str, password: str):
        return self.__class__(username, password)

    @abstractmethod
    def subsume_from_master(self, master: 'AuthHandler'):
        pass


class NoAuthHandler(AuthHandler):

    def __init__(self):
        super().__init__('no', 'auth')

    def subsume_from_master(self, master: AuthHandler):
        pass

    def authorize_request(self, request):
        pass

    def make_authorization_header(self) -> str:
        pass


class HttpBasicAuthHandler(AuthHandler):

    def authorize_request(self, request):
        request.headers['Authorization'] = self.make_authorization_header()

    def make_authorization_header(self) -> str:
        credentials = f'{self.username}:{self.password}'
        basic = base64.b64encode(credentials.encode()).decode()
        return f'Basic {basic}'

    def subsume_from_master(self, master: AuthHandler):
        # It is just a coincidence that all available authentication types have
        # username and password.
        self.username = master.username
        self.password = master.password


class HttpDigestAuthHandler(AuthHandler):

    def __init__(self, username: str, password: str):
        super().__init__(username, password)
        self._challenge: Optional[Mapping[str, str]] = None

    def authorize_request(self, request):
        if self._challenge is None:
            raise _CannotAuthorizeRequest("Digest challenge not yet received")
        path = urllib.parse.urlparse(request.url).path
        digest = calculate_digest(
            request.method,
            path,
            self._challenge['realm'],
            self._challenge['nonce'],
            self.username,
            self.password,
            )
        request.headers['Authorization'] = (
            'Digest '
            f'username={self._quote(self.username)}, '
            f'realm={self._quote(self._challenge["realm"])}, '
            f'nonce={self._quote(self._challenge["nonce"])}, '
            f'uri={self._quote(path)}, '
            f'response={self._quote(digest)}, '
            f'algorithm="MD5"')

    @staticmethod
    def _quote(value: str) -> str:
        return '"' + value + '"'

    def make_authorization_header(self) -> str:
        raise NotImplementedError(
            "Digest authentication requires request information to make Authorization header")

    def subsume_from_master(self, master: AuthHandler):
        # It is just a coincidence that all available authentication types have
        # username and password.
        self.username = master.username
        self.password = master.password

    def handle_failed_request(self, request, response):
        if response.status_code == 401:
            self._handle_401(request, response)
        else:
            raise CannotHandleRequest(f"Handling of {response.status_code} not supported")

    def _handle_401(self, request: _HttpRequest, response: _HttpResponse):
        challenge = response.headers.get('WWW-Authenticate')
        if not challenge:
            raise _CannotAuthorizeRequest("Response doesn't contain Digest challenge")
        self._set_challenge(challenge)
        self.authorize_request(request)

    def _set_challenge(self, raw_challenge: str):
        _, challenge = raw_challenge.split(' ', 1)
        keqv_list = [x for x in urllib.request.parse_http_list(challenge) if x]
        self._challenge = urllib.request.parse_keqv_list(keqv_list)


class HttpBearerAuthHandler(AuthHandler):

    def __init__(self, username: str, password: str, token_provider: 'TokenProvider'):
        super().__init__(username, password)
        self._token_provider = token_provider
        self._token: Optional[str] = None
        self._refresh_old_token = True

    def authorize_request(self, request):
        request.headers['Authorization'] = self.make_authorization_header()

    def make_authorization_header(self) -> str:
        return f'Bearer {self.get_token()}'

    def get_token(self) -> str:
        if self._token is None:
            self.refresh_token()
        return self._token

    def refresh_token(self):
        self._token = self._token_provider.obtain_token(self.username, self.password)

    def subsume_from_master(self, master: 'HttpBearerAuthHandler'):
        """Copy username and password, leaving token the same.

        If, after merging, the slave decides to reject the token, a new token
        will be re-issued by the slave.
        """
        # It is just a coincidence that all available authentication types have
        # username and password.
        self.username = master.username
        self.password = master.password
        if master._token_provider.must_be_subsumed():
            self._token_provider = master._token_provider

    def handle_failed_request(self, request, response):
        if response.status_code == 401:
            self._handle_401(request)
        elif response.status_code == 403:
            self._handle_403(request, response)
        else:
            raise CannotHandleRequest(f"Handling of {response.status_code} not supported")

    def _handle_401(self, request):
        if self._token is not None:
            if not self._refresh_old_token:
                raise _CannotAuthorizeRequest("No need to refresh old token")
        self.refresh_token()
        self.authorize_request(request)

    def _handle_403(self, request: _HttpRequest, response: _HttpResponse):
        auth_result_header = response.headers.get('x-auth-result', '')
        if auth_result_header == 'Auth_WrongSessionToken':
            if self._token is not None:
                if not self._refresh_old_token:
                    raise _CannotAuthorizeRequest("No need to refresh old token")
            # Request requires a fresh token (not older than 10 minutes).
            self.refresh_token()
            self.authorize_request(request)
        else:
            raise CannotHandleRequest("This 403 response is not related to the validity of token")

    def with_credentials(self, username: str, password: str):
        return self.__class__(username, password, self._token_provider)

    def enable_refresh_old_token(self):
        self._refresh_old_token = True

    def disable_refresh_old_token(self):
        self._refresh_old_token = False


class TokenProvider(Protocol):

    def obtain_token(self, username: str, password: str) -> str:
        ...

    @staticmethod
    def must_be_subsumed() -> bool:
        ...


class CannotHandleRequest(Exception):
    pass


class _CannotAuthorizeRequest(CannotHandleRequest):
    pass


class CannotObtainToken(_CannotAuthorizeRequest):
    pass


class HttpReadTimeout(Exception):
    pass


class HttpConnectionError(Exception):
    pass
