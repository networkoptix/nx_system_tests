# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import http.client
import json
import logging
from abc import ABCMeta
from abc import abstractmethod
from typing import Any
from typing import Literal
from typing import Optional
from typing import Tuple
from urllib.parse import urlsplit


class GitLabConnection:
    """Reused GitLab connection; optimizes transatlantic communication.

    At the time of writing, GitLab is located in Europe, but the DC, where
    everything else runs, is located in the USA.

    TCP and TLS handshakes take 350 ms in total, which greatly limits overall
    throughput.

    This class also wraps http.client.HTTPConnection with classes that have
    smaller interface surface.
    """

    def __init__(self, url: str):
        self._raw_url = url
        self._parsed_url = urlsplit(url)
        self._conn: Optional[http.client.HTTPConnection] = None
        self._reconnect()

    def __repr__(self):
        return f'{self.__class__.__name__}({self._raw_url!r})'

    def request(self, req: '_Request') -> '_Response':
        try:
            return self._request(req)
        except (ConnectionResetError, BrokenPipeError, TimeoutError) as e:
            _logger.error(e)
            self._reconnect()
            return self._request(req)

    def _request(self, req: '_Request') -> '_Response':
        req.make(self._conn)
        return _Response(self._conn)

    def _reconnect(self):
        if self._conn is not None:
            self._conn.close()
        netloc = self._parsed_url.netloc
        timeout = 20
        if self._parsed_url.scheme == 'https':
            self._conn = http.client.HTTPSConnection(netloc, timeout=timeout)
        else:
            self._conn = http.client.HTTPConnection(netloc, timeout=timeout)


class _Response:
    """Handle headers and data; required for connection reuse.

    If a connection is reused, the response body must be read out completely
    from the connection before making the next request and response. Otherwise,
    when doing the next request, the code expecting response headers will
    receive the previous response body. This detail is often neglected with
    one-shot connections - the body is read only if needed. This class forces
    reading out the body.

    Headers and body are encapsulated in a single object.
    """

    def __init__(self, conn: http.client.HTTPConnection):
        self._response = conn.getresponse()
        self._data = self._response.read()

    def status(self) -> int:
        return self._response.status

    def json(self):
        data = self._data.decode()
        data = json.loads(data)
        return data

    def raw(self):
        return self._data

    def range(self) -> Tuple[int, Optional[int]]:
        """Parse "Range: 0-123" - malformed header from GitLab."""
        r = self._response.headers['Range']
        start, end = r.strip().split('-')
        start = int(start)
        end = int(end) if end else None
        return start, end


class _Request(metaclass=ABCMeta):

    @abstractmethod
    def make(self, conn: http.client.HTTPConnection):
        pass


class GitLabGenericRequest(_Request):

    def __init__(self, method: '_Method', path: str, data: bytes, headers=None):
        self._path = path
        self._method = method
        self._data: bytes = data
        self._headers = headers if headers is not None else {}

    def make(self, conn: http.client.HTTPConnection):
        conn.request(
            self._method,
            self._path,
            body=self._data,
            headers={
                'Connection': 'keep-alive',
                **self._headers,
                },
            )


class GitLabJSONRequest(GitLabGenericRequest):

    def __init__(self, method: '_Method', path: str, json_data: Any):
        data = json.dumps(json_data).encode()
        mime_header = {'Content-Type': 'application/json'}
        super().__init__(method, path, data, headers=mime_header)


_Method = Literal['POST', 'PUT', 'PATCH']

_logger = logging.getLogger(__name__)
