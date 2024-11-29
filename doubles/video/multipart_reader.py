# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import cgi
import io
import logging
import pathlib
import socket
from typing import Optional
from typing import Sequence
from urllib.parse import urlparse

from ca import default_ca
from doubles.software_cameras import JpegImage
from mediaserver_api import MediaserverApiV0

_logger = logging.getLogger(__name__)


def _parse_status(fp):
    headline = fp.readline()
    if not headline:
        raise RuntimeError(
            "Connection closed when reading headline of HTTP/MPJPEG stream; "
            "server may have crashed or handled an exception poorly")
    headline = headline.rstrip()
    headline = headline.decode('iso-8859-1')
    proto, code, message = headline.split(maxsplit=2)
    code = int(code)
    return proto, code, message


def _parse_headers(fp):
    headers = {}
    while True:
        header = fp.readline()
        header = header.rstrip()
        if not header:
            break
        header = header.decode('iso-8859-1')
        field, value = header.split(':', 1)
        field = field.strip().title()
        value, params = cgi.parse_header(value)
        if field in headers:
            pass
            # raise RuntimeError("Duplicate header {}".format(field))
        headers[field] = value, params
    return headers


class _SourceClosed(Exception):
    pass


class _ChunkedReader:

    def __init__(self, fp):
        self._fp = fp
        self._left_in_current_chunk = 0
        self.closed = False

    def readinto(self, buffer):
        assert len(buffer) > 0
        if self.closed:
            raise RuntimeError("No more content")
        if self._left_in_current_chunk > 0:
            to_read = min(len(buffer), self._left_in_current_chunk)
            data = self._fp.read(to_read)
            assert len(data) == to_read
            del to_read
            self._left_in_current_chunk -= len(data)
            assert self._left_in_current_chunk >= 0
            buffer[:len(data)] = data
            return len(data)
        while True:
            line = self._fp.readline()
            line = line.rstrip()
            if line:
                break
            if self._fp.closed:
                raise _SourceClosed("Can't get any more data from buffer")
        chunk_size = int(line, base=16)
        if chunk_size == 0:
            self.trailer = _parse_headers(self._fp)
            self.closed = True
            return 0
        to_read = min(len(buffer), chunk_size)
        data = self._fp.read(to_read)
        assert len(data) == to_read
        del to_read
        buffer[:len(data)] = data
        self._left_in_current_chunk = chunk_size - len(data)
        assert self._left_in_current_chunk >= 0
        return len(data)


class _BufferedReader:

    def __init__(self, fp):
        self._fp = fp
        self._buffer = bytearray(65535)
        self._start, self._end = 0, 0
        self.closed = False

    def _find(self, substring):
        return self._buffer.index(substring, self._start, self._end)

    def _cut(self, end):
        assert self._start <= end <= self._end
        result = memoryview(self._buffer)[self._start:end]
        self._start = end
        return result

    def _load(self):
        # Each byte is copied at most twice on average.
        data = memoryview(self._buffer)[self._start:self._end]
        # TODO: When to reallocate?
        if len(self._buffer) - self._end < max(4096, len(data)):
            # TODO: Buffer should be twice as large as max read_size.
            new_buffer_length = max(len(self._buffer), 2 * len(data))
            self._buffer = bytearray(new_buffer_length)
            self._start, self._end = 0, len(data)
            self._buffer[self._start:self._end] = data
        assert self._end < len(self._buffer)
        read_size = self._fp.readinto(memoryview(self._buffer)[self._end:])
        self._end += read_size
        return read_size

    def readuntil(self, delim):  # Mimic readline name.
        if self.closed:
            return b''
        while True:
            try:
                found_at = self._find(delim)
            except ValueError:
                loaded = self._load()
                if loaded == 0:  # Underlying stream is closed.
                    self.closed = True
                    return self._cut(self._end)
            else:
                return self._cut(found_at + len(delim))

    def readline(self):
        if self.closed:
            return b''
        return bytes(self.readuntil(b'\r\n'))

    def read(self, size):
        if self.closed:
            return b''
        while True:
            if self._end - self._start >= size:
                return self._cut(self._start + size)
            read_size = self._load()
            if read_size == 0:  # Underlying stream is closed.
                self.closed = True
                return b''


class ConnectionClosed(Exception):
    pass


class MultiPartReader:

    def __init__(self, url, auth_header: Optional[str] = None):
        parsed_url = urlparse(url)
        sock = socket.socket()
        sock = default_ca().wrap_client_socket(sock)
        sock.settimeout(20)
        sock.connect((parsed_url.hostname, parsed_url.port or 80))
        sock.send(b'GET ' + url.encode('iso-8859-1') + b' HTTP/1.1\r\n')
        if auth_header is not None:
            sock.send(b'Authorization: ' + auth_header.encode('iso-8859-1') + b'\r\n')
        elif parsed_url.username:
            credentials = parsed_url.username + ':' + parsed_url.password
            auth = base64.b64encode(credentials.encode('utf8'))
            sock.send(b'Authorization: Basic ' + auth + b'\r\n')
        sock.send(b'\r\n')
        self._http_io = _BufferedReader(sock.makefile(buffering=0, mode='rb'))
        self.proto, self.code, self.message = _parse_status(self._http_io)
        if self.code != 200:
            raise RuntimeError(f"Response status is not 200 OK: {self.code}")
        _logger.debug("Connection established: %s", sock)
        self.headers = _parse_headers(self._http_io)
        encoding, _ = self.headers.get('Transfer-Encoding', ('identity', {}))
        _logger.debug("Headers received: %s", self.headers)
        if encoding == 'chunked':
            self._data_io = _BufferedReader(_ChunkedReader(self._http_io))
        else:
            self._data_io = self._http_io
        self.preamble = b''
        # VMS-14998: Get boundary from data. Mediaserver sends a wrong one.
        while True:
            line = self._data_io.readline()
            if line.startswith(b'--'):
                self.boundary = line.rstrip()[2:].decode('iso-8859-1')  # Remove exactly two.
                break
            self.preamble += line
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration()
        # Don't trust Content-Length, VLC messes up with it.
        # Also, the epilogue doesn't contain headers, so the headers cannot be
        # parsed before the boundary is reached.
        delim = b'\r\n--' + self.boundary.encode('iso-8859-1') + b'\r\n'
        try:
            chunk = self._data_io.readuntil(delim)
        except _SourceClosed:
            _logger.debug("Stop: source buffer is closed")
            self.epilogue = None
            self.closed = True
            raise ConnectionClosed()
        if chunk[-len(delim):] != delim:  # No endswith in memoryview.
            _logger.debug("Stop: finished successfully")
            self.epilogue = bytes(chunk)
            self.closed = True
            raise StopIteration()
        part = chunk[:-len(delim)]
        part_io = io.BytesIO(part)
        headers = _parse_headers(part_io)
        contents = part[part_io.tell():]
        return headers, contents


def get_frames(url: str, auth_header: Optional[str] = None) -> Sequence[JpegImage]:
    _logger.info("Get frames: %s", url)
    stream = MultiPartReader(url, auth_header=auth_header)
    _logger.debug("Preamble: %r", stream.preamble)
    boundary_in_header = stream.headers['Content-Type'][1]['boundary']
    if stream.boundary != boundary_in_header:
        raise RuntimeError(
            "Content-Type boundary differs from actual: "
            f"{boundary_in_header} != {stream.boundary}")
    result = []
    for headers, frame in stream:
        if 'Content-Length' in headers:
            content_len_in_header = int(headers['Content-Length'][0])
            if content_len_in_header != len(frame):
                _logger.error(
                    "Content-Length differs from actual: %d != %d",
                    content_len_in_header, len(frame))
        result.append(JpegImage(frame))
    if stream.epilogue is None:
        _logger.error("Epilogue: N/A; stream timed out")
    elif len(stream.epilogue) < 2000:
        _logger.debug("Epilogue: %r", stream.epilogue)
    else:
        _logger.error(
            "Epilogue too big: %r and %d bytes more",
            stream.epilogue[:100], len(stream.epilogue) - 100)
    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    api = MediaserverApiV0('https://admin:WellKnownPassword2@127.0.0.1:25011/')
    [camera, *_] = api.http_get('ec2/getCamerasEx')
    [[*_, period]] = api.list_recorded_periods([camera['id']])
    url = api.mpjpeg_url(camera['id'], period)
    client = MultiPartReader(url)
    logging.info("Preamble: %s", client.preamble.decode(errors='namereplace'))
    for i, (_headers, frame) in enumerate(client):
        path = pathlib.Path('{:03d}.jpg'.format(i))
        logging.info("Frame: %s", path.absolute())
        path.write_bytes(frame)
    logging.info("Epilogue: %s", client.epilogue.decode(errors='namereplace'))
