# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import io
import logging
import socket
import ssl
import struct
import time
from abc import ABCMeta
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from email.message import Message
from email.parser import FeedParser
from typing import Any
from typing import BinaryIO
from typing import List
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Tuple
from urllib.parse import urlparse

from doubles.software_cameras import FrameSize
from doubles.software_cameras import JpegImage

_logger = logging.getLogger(__name__)

_rtsp_default_port = 554
_payload_type_mjpeg = 26


class _JpegMainHeader(NamedTuple):
    type_specific: int
    fragment_offset: int
    type: int
    quantization: int
    width: int
    height: int


class _QuantizationTablesHeader(NamedTuple):
    mbz: int  # Must be zero
    precision: int
    length: int


class _MotionJpegStream:

    def __init__(self):
        self._frames: List[JpegImage] = []
        self._current_frame_raw = b''
        self._quantization_tables = None

    @staticmethod
    def _parse_jpeg_header(jpeg_header_raw: bytes) -> _JpegMainHeader:
        jpeg_header_data = struct.unpack('>B3sBBBB', jpeg_header_raw)
        [type_specific, frame_offset, type_, quantization, width, height] = jpeg_header_data
        return _JpegMainHeader(
            type_specific,
            int.from_bytes(frame_offset, 'big'),
            type_,
            quantization,
            width * 8,
            height * 8)

    @staticmethod
    def _parse_quantization_tables_header(
            quantization_tables_header: bytes) -> _QuantizationTablesHeader:
        quantization_tables_data = struct.unpack('>BBH', quantization_tables_header)
        return _QuantizationTablesHeader(*quantization_tables_data)

    def parse_frame(self, jpeg_data_raw: bytes, end_of_frame: bool) -> Optional[JpegImage]:
        with io.BytesIO(jpeg_data_raw) as buffer:
            jpeg_header_raw = buffer.read(8)
            jpeg_header = self._parse_jpeg_header(jpeg_header_raw)
            if jpeg_header.type != 1:
                raise NotImplementedError("Only type 1 is supported")
            if jpeg_header.fragment_offset == 0:
                quantization_tables_header_raw = buffer.read(4)
                quantization_tables_header = self._parse_quantization_tables_header(
                    quantization_tables_header_raw)
                if quantization_tables_header.mbz != 0:
                    raise RuntimeError(f"Non-zero MBZ field: {quantization_tables_header.mbz}")
                if quantization_tables_header.precision != 0:
                    raise NotImplementedError("Only precision value 0 is supported")
                # Precision value 0 and type 1 mean that there are two 64-byte quantization tables:
                # one for the luminance component and one for the chrominance component.
                if quantization_tables_header.length != 128:
                    raise RuntimeError(
                        f"Quantization tables length must be 128 bytes, "
                        f"not {quantization_tables_header.length}")
                self._quantization_tables = buffer.read(quantization_tables_header.length)
            self._current_frame_raw += buffer.read()
        if end_of_frame:
            if self._quantization_tables is None:
                raise RuntimeError("No quantization tables in frame")
            complete_frame = JpegImage.from_data(
                self._quantization_tables,
                jpeg_header.width,
                jpeg_header.height,
                scan=self._current_frame_raw,
                )
            self._current_frame_raw = b''
            self._quantization_tables = None
            return complete_frame
        return None


class _RtspUnexpectedStatus(Exception):
    pass


class ConnectionClosedByServer(Exception):
    pass


class _StreamClosed(Exception):
    pass


class _GotEnough(Exception):
    pass


class _StatusLine(NamedTuple):
    protocol: bytes
    code: int
    status: bytes


def _read_buffered(stream: BinaryIO, to_read: int) -> bytes:
    received_bytes = stream.read(to_read)
    if len(received_bytes) < to_read:
        raise _StreamClosed("Connection is closed by the remote host")
    return received_bytes


class _RtspResponse:

    def __init__(self, status_line: _StatusLine, headers: Message, data: bytes):
        self.status_line = status_line
        self.headers = headers
        self.data = data

    def raise_for_status(self):
        if self.status_line.code == 401:
            raise _UnauthorizedError(self)
        if self.status_line.code != 200:
            raise _RtspUnexpectedStatus(
                f"Unexpected RTSP status: {self.status_line.code} {self.status_line.status}")

    @classmethod
    def read_from(cls, stream: BinaryIO, status_line_prefix: bytes = b''):
        status_line_rest = stream.readline().strip()
        status_line_raw = status_line_prefix + status_line_rest
        [protocol, code, status] = status_line_raw.split(maxsplit=2)
        status_line = _StatusLine(protocol, int(code), status)
        headers = _read_headers(stream)
        data = b''
        content_length = int(headers.get('Content-Length', 0))
        if content_length > 0:
            data = _read_buffered(stream, content_length)
        return _RtspResponse(status_line, headers, data)


class _UnauthorizedError(_RtspUnexpectedStatus):

    def __init__(self, response: _RtspResponse):
        self.response = response


class _RtspInterleavedFrameHeader(NamedTuple):
    magic_number: bytes
    channel: bytes
    data_length: int


class _RtpHeader(NamedTuple):
    rtp_version: int
    marker: bool
    payload_type: int
    sequence_number: int
    timestamp: int
    ssrc: int


def _parse_rtp_header(rtp_header_raw: bytes) -> _RtpHeader:
    rtp_data = struct.unpack('>BBHII', rtp_header_raw)
    [first_byte, marker_and_payload_type, sequence_number, timestamp, ssrc] = rtp_data
    rtp_version = first_byte >> 6  # Rightmost 6 bits are unused
    marker = marker_and_payload_type >> 7
    payload_type = marker_and_payload_type & 0b01111111
    return _RtpHeader(rtp_version, bool(marker), payload_type, sequence_number, timestamp, ssrc)


def _wrap_ssl_socket(sock: socket.socket) -> ssl.SSLSocket:
    ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE  # To prevent self-signed certificate verification error
    return ssl_context.wrap_socket(sock)


def _read_headers(stream: BinaryIO) -> Message:
    headers_raw = b''.join(iter(stream.readline, b'\r\n'))
    parser = FeedParser()
    parser.feed(headers_raw.decode('ascii', errors='surrogateescape'))
    return parser.close()


class _MJPEGStreamInfo(NamedTuple):
    frame_size: FrameSize
    fps: float


class _RTPJPEGChannel:

    def __init__(self, id_: int):
        if (id_ // 2) > 0:
            raise RuntimeError(f"rtp_channel_id must be even. Odd value {id_} received")
        self.id = id_
        self._frames: List[JpegImage] = []
        self._video_stream = _MotionJpegStream()
        self._first_received: float = 0.0
        self._last_received: float = 0.0

    def get_stream_info(self) -> _MJPEGStreamInfo:
        fps = self._get_actual_fps()
        resolution = self._get_actual_resolution()
        return _MJPEGStreamInfo(resolution, fps)

    def _get_actual_fps(self) -> float:
        if self._last_received == self._first_received == 0.0:
            raise RuntimeError("Stream is not started")
        delta_seconds = self._last_received - self._first_received
        return (len(self._frames) - 1) / delta_seconds

    def _get_actual_resolution(self):
        try:
            first_frame = self._frames[0]
        except IndexError:
            raise RuntimeError("Stream is not started, can't find any frames")
        return first_frame.frame_size

    def _update_frame_arrival_times(self):
        now = time.monotonic()
        if not self._first_received:
            self._first_received = now
        self._last_received = now

    def put_raw(self, raw: bytes):
        rtp_header_length = 12
        rtp_header_raw = raw[:rtp_header_length]
        video_data_raw = raw[rtp_header_length:]
        rtp_header = _parse_rtp_header(rtp_header_raw)
        if rtp_header.payload_type == _payload_type_mjpeg:
            complete_frame = self._video_stream.parse_frame(
                video_data_raw, end_of_frame=rtp_header.marker)
            if complete_frame is not None:
                self._frames.append(complete_frame)
            self._update_frame_arrival_times()
        else:
            raise NotImplementedError(
                f"Only MJPEG (type {_payload_type_mjpeg}) is supported by RTSP client")

    def get_full_stream(self) -> Sequence[JpegImage]:
        return self._frames


class _RtspRequest:

    def __init__(self, method: str, url: str):
        self.url = url
        self.method = method
        self._headers = {'User-Agent': 'NX-FT-RTSP-CLIENT'}

    def update_headers(self, headers: Mapping[str, str]):
        self._headers.update(headers)

    def get_header(self, key: str) -> Optional[str]:
        return self._headers.get(key)

    def serialize(self):
        headline = f'{self.method} {self.url} RTSP/1.0'
        header_string_list = list(f'{key}: {value}' for key, value in self._headers.items())
        headers_string = '\r\n'.join(header_string_list)
        request = f'{headline}\r\n{headers_string}\r\n\r\n'
        return request.encode('utf-8')

    def __repr__(self):
        return f'<RTSP {self.method}: {self.url} Headers: {self._headers}>'


class _RTSPSession:

    def __init__(self, id_: str, url: str, timeout: int):
        self._id = id_
        self._url = url
        self._timeout = timeout
        self._next_activity = 0
        self._update_activity()

    def _update_activity(self):
        session_timeout_threshold = self._timeout / 2
        self._next_activity = time.monotonic() + session_timeout_threshold

    def is_idle(self) -> bool:
        return self._next_activity < time.monotonic()

    def get_request(self, method: str) -> _RtspRequest:
        request = _RtspRequest(method, self._url)
        request.update_headers({'Session': self._id})
        logging.info("%r: %s", self, request)
        self._update_activity()
        return request

    def __repr__(self):
        return f"<RTSP Session {self._id}>"


class _RtspAuth(metaclass=ABCMeta):

    @abstractmethod
    def set_auth_info(self, request: _RtspRequest):
        pass

    @abstractmethod
    def handle_unauthorised(self, response: _RtspResponse):
        pass


class _NoopAuth(_RtspAuth):

    def set_auth_info(self, request):
        pass

    def handle_unauthorised(self, response):
        raise RuntimeError(
            f"Received Unauthorised response {response} while no authentication is provided")


class _BearerAuth(_RtspAuth):

    def __init__(self, bearer: str):
        self._bearer = bearer

    def set_auth_info(self, request):
        request.update_headers({'Authorization': self._bearer})

    def handle_unauthorised(self, response):
        raise RuntimeError(f"Received Unauthorised response {response} for bearer {self._bearer}")


class _DigestAuth(_RtspAuth):

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self._realm: Optional[str] = None
        self._nonce: Optional[str] = None
        self._user_digest: Optional[str] = None

    def _raise_at_wrong_state(self):
        if self._realm is None and self._nonce is not None:
            raise RuntimeError(f"realm is None but nonce is not: {self._nonce}")
        elif self._realm is not None and self._nonce is None:
            raise RuntimeError(f"nonce is None but realm is not: {self._realm}")
        elif self._user_digest is None:
            raise RuntimeError("User digest is None")

    @staticmethod
    def _quote(value: str) -> str:
        # TODO: Quote according to RFC 2068 section 2
        return '"' + value + '"'

    def _calculate_user_digest(self) -> str:
        digest_string = ':'.join([self._username.lower(), self._realm, self._password])
        return hashlib.md5(digest_string.encode()).hexdigest()

    def _calculate_auth_header(self, method: str, url: str) -> str:
        self._raise_at_wrong_state()
        ha2 = hashlib.md5(':'.join([method, url]).encode()).hexdigest()
        digest = hashlib.md5(':'.join([self._user_digest, self._nonce, ha2]).encode()).hexdigest()
        return (
            'Digest '
            f'username={self._quote(self._username)} '
            f'realm={self._quote(self._realm)} '
            f'nonce={self._quote(self._nonce)} '
            f'uri={self._quote(url)} '
            f'response={self._quote(digest)} '
            )

    def set_auth_info(self, request):
        authorization = self._calculate_auth_header(method=request.method, url=request.url)
        request.update_headers({'Authorization': authorization})

    @staticmethod
    def _parse_authentication_header(header: str) -> Tuple[str, str]:
        [_, values] = header.split('Digest ')
        [realm_key_val, nonce_key_val, _] = values.split(', ')
        return realm_key_val.split('=')[1].strip('"\''), nonce_key_val.split('=')[1].strip('"\'')

    def _set_state_variables(self, realm: str, nonce: str):
        self._realm = realm
        self._nonce = nonce
        self._user_digest = self._calculate_user_digest()

    def handle_unauthorised(self, response):
        x_auth_result_header = response.headers.get('X-Auth-Result')
        www_authenticate_header = response.headers.get('WWW-Authenticate')
        if x_auth_result_header is None:
            raise RuntimeError(f"X-Auth-Result header is not received: {response}")
        if www_authenticate_header is None:
            raise RuntimeError(f"WWW-Authenticate header is not received: {response}")
        realm, nonce = self._parse_authentication_header(www_authenticate_header)
        self._set_state_variables(realm, nonce)
        _logger.info(
            "Obtained realm %s and nonce %s from %s. User digest: %s",
            self._realm, self._nonce, response, self._user_digest)


class _RtspClient:

    def __init__(self, url: str, auth_header: Optional[str] = None):
        parsed_url = urlparse(url)
        _, _, host_info = parsed_url.netloc.rpartition('@')
        self._url = parsed_url._replace(netloc=host_info).geturl()
        sock = socket.socket()
        if parsed_url.scheme == 'rtsp':
            self._sock = sock
        elif parsed_url.scheme == 'rtsps':
            self._sock = _wrap_ssl_socket(sock)
        else:
            raise RuntimeError(
                f"Only 'rtsp' or 'rtsps' schemes are supported. Received: {parsed_url.scheme}")
        self._sock.settimeout(5)  # Expect server to reply
        server_address = (parsed_url.hostname, parsed_url.port or _rtsp_default_port)
        self._sock.connect(server_address)
        _logger.info("New connection to %r", server_address)
        self._stream = self._sock.makefile('rwb')
        self._cseq = 0
        self._rtp_channel = _RTPJPEGChannel(0)
        self._rtcp_channel_id = 1
        if auth_header is None:
            username, password = parsed_url.username, parsed_url.password
            if username is not None:
                if password is None:
                    raise RuntimeError(f"Username is present: {username} but password is None")
                self._auth_handler = _DigestAuth(username, password)
            self._auth_handler = _NoopAuth()
        else:
            self._auth_handler = _BearerAuth(auth_header)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self._stream.close()
        self._sock.close()

    def _read_buffered(self, to_read: int) -> bytes:
        return _read_buffered(self._stream, to_read)

    @staticmethod
    def _parse_sdp(sdp_description: str) -> Mapping[str, Any]:
        headers = [h for h in sdp_description.splitlines() if h != '']
        media_info = {}
        for header in headers:
            [key, value] = header.split('=', maxsplit=1)
            if key == 'a':  # There can be multiple media attribute headers
                [media_attribute_key, media_attribute_value] = value.split(':', maxsplit=1)
                media_info.setdefault('a', {})[media_attribute_key] = media_attribute_value
                continue
            media_info[key] = value
        return media_info

    def _send_request(self, request: _RtspRequest):
        self._auth_handler.set_auth_info(request)
        request.update_headers({'CSeq': str(self._cseq)})
        request_raw = request.serialize()
        _logger.debug("Make RTSP request:")
        for line in request_raw.splitlines():
            _logger.debug("  %r", line)
        self._stream.write(request_raw)
        self._stream.flush()
        self._cseq += 1

    def _make_request(
            self,
            method: str,
            url: str,
            headers: Optional[Mapping[str, str]] = None,
            ) -> _RtspResponse:
        request = _RtspRequest(method, url)
        if headers is not None:
            request.update_headers(headers)
        self._auth_handler.set_auth_info(request)
        self._send_request(request)
        response = _RtspResponse.read_from(self._stream)
        try:
            response.raise_for_status()
        except _UnauthorizedError as e:
            self._auth_handler.handle_unauthorised(e.response)
            self._auth_handler.set_auth_info(request)
            self._send_request(request)
            response = _RtspResponse.read_from(self._stream)
            response.raise_for_status()
        return response

    def _options(self):
        response = self._make_request('OPTIONS', self._url)
        options = response.headers['Public'].split(', ')
        for option in ['DESCRIBE', 'SETUP', 'PLAY', 'TEARDOWN']:
            if option not in options:
                raise RuntimeError(
                    f"Option {option} is not available; Available options: {options}")

    def _get_rtsp_response(self) -> _RtspResponse:
        response = _RtspResponse.read_from(self._stream)
        response.raise_for_status()
        return response

    def _open_session(self) -> _RTSPSession:
        response = self._make_request('DESCRIBE', self._url, headers={'Accept': 'application/sdp'})
        content_type = response.headers.get('Content-Type')
        if content_type is None:  # Some servers return lower-case 'type'
            content_type = response.headers.get('Content-type')
        if content_type != 'application/sdp':
            raise RuntimeError(f"Content-Type is not 'application/sdp': {content_type}")
        session_header = response.headers['Session']
        session_id, timeout_raw = session_header.split(';')
        field, timeout = timeout_raw.split('=')
        if field != 'timeout':
            raise RuntimeError(f"Inconsistent Session header {session_header}")
        media_info = self._parse_sdp(response.data.decode('utf-8'))
        if media_info['m'] != 'video 0 RTP/AVP 26':
            raise NotImplementedError("Only MJPEG codec is supported at the moment")
        content_base_url = response.headers.get('Content-Base')
        if content_base_url is None:
            session_url = self._url
        else:
            track_id = media_info['a']['control']
            session_url = content_base_url.rstrip('/') + '/' + track_id
        logging.info(
            "New RTSP session ID: %s, session_url: %s, timeout: %s",
            session_id, session_url, timeout)
        return _RTSPSession(session_id, session_url, int(timeout))

    def _setup(self, session: _RTSPSession):
        setup_request = session.get_request('SETUP')
        channels = f'interleaved={self._rtp_channel.id}-{self._rtcp_channel_id}'
        setup_headers = {'Transport': f'RTP/AVP/TCP;unicast;{channels}'}  # Only TCP is supported
        setup_request.update_headers(setup_headers)
        self._send_request(setup_request)
        self._get_rtsp_response()

    def _play(self, session: _RTSPSession):
        play_request = session.get_request('PLAY')
        self._send_request(play_request)
        self._get_rtsp_response()

    def _send_teardown(self, session: _RTSPSession):
        teardown_request = session.get_request('TEARDOWN')
        self._send_request(teardown_request)

    def _collect_stream_residue(self):
        while True:
            try:
                first_four_bytes = self._read_buffered(4)
            except TimeoutError:
                logging.warning(
                    "Stream finished, but TCP connection is not closed. "
                    "It is OK with Mediaserver")
                break
            except _StreamClosed:
                logging.info("Stream is closed")
                break
            if first_four_bytes == b'RTSP':
                response = _RtspResponse.read_from(self._stream, first_four_bytes)
                logging.info("Got unexpected response: %s  Probably is teardown", response)
                response.raise_for_status()
            else:
                self._read_interleaved_frame(first_four_bytes)

    def _read_interleaved_frame(self, frame_header: bytes):
        interleaved_frame_header = _RtspInterleavedFrameHeader(
            *struct.unpack('>cBH', frame_header))
        if interleaved_frame_header.magic_number != b'$':
            raise RuntimeError(f"Magic number mismatch: {interleaved_frame_header}")
        _logger.debug("Read %d bytes frame", interleaved_frame_header.data_length)
        if interleaved_frame_header.channel == self._rtcp_channel_id:
            _logger.debug("Got RTCP frame; Ignore it")
            self._read_buffered(interleaved_frame_header.data_length)
        elif interleaved_frame_header.channel == self._rtp_channel.id:
            interleaved_frame_raw = self._read_buffered(interleaved_frame_header.data_length)
            self._rtp_channel.put_raw(interleaved_frame_raw)
        else:
            raise RuntimeError(f"Unknown RTSP channel: {interleaved_frame_header.channel}")

    def _read_stream(self, session: _RTSPSession, time_limit_sec: float):
        _logger.info("Start getting stream")
        started_at = time.monotonic()
        while True:
            # Some servers (like Nx FT camera server) doesn't close the TCP connection after
            # stream is over. In that case TimeoutError raised on sock.recv().
            try:
                first_four_bytes = self._read_buffered(4)
            except TimeoutError:
                sock_timeout = self._sock.gettimeout()
                _logger.warning("Reading from socket timed out: %.1f sec", sock_timeout)
                stream_duration_sec = time.monotonic() - started_at - sock_timeout
                break
            # Some servers (like Nx mediaserver) closes the TCP connection after stream is over.
            except _StreamClosed:
                _logger.info("TCP stream closed on remote side")
                stream_duration_sec = time.monotonic() - started_at
                break
            if first_four_bytes == b'RTSP':
                response = _RtspResponse.read_from(self._stream, first_four_bytes)
                logging.info("Got unexpected response: %s  Probably is teardown", response)
                response.raise_for_status()
            else:
                self._read_interleaved_frame(first_four_bytes)
            stream_duration_sec = time.monotonic() - started_at
            if stream_duration_sec >= time_limit_sec:
                _logger.info("Got %.2f seconds of stream; Stop getting stream", stream_duration_sec)
                raise _GotEnough()
            if session.is_idle():
                logging.info("%r: Keep alive with OPTIONS", session)
                options_request = session.get_request('OPTIONS')
                self._send_request(options_request)
        duration_tolerance = 1
        if time_limit_sec - stream_duration_sec > duration_tolerance:
            raise ConnectionClosedByServer(
                "Stream ended before time limit exceeded; "
                f"Duration expected: {time_limit_sec}; "
                f"Actual duration: {stream_duration_sec:.2f}")

    def receive_stream(self, time_limit_sec):
        self._options()
        session = self._open_session()
        self._setup(session)
        self._play(session)
        try:
            self._read_stream(session, time_limit_sec)
        except _GotEnough:
            self._send_teardown(session)
            self._collect_stream_residue()

    def get_stream(self) -> Sequence[JpegImage]:
        return self._rtp_channel.get_full_stream()

    def get_stream_info(self) -> _MJPEGStreamInfo:
        return self._rtp_channel.get_stream_info()


def get_rtsp_stream(
        url: str,
        time_limit_sec: float = float('inf'),
        auth_header: Optional[str] = None) -> Sequence[JpegImage]:
    _logger.info("Get %.3f seconds of stream: %s", time_limit_sec, url)
    with _RtspClient(url, auth_header=auth_header) as client:
        try:
            client.receive_stream(time_limit_sec)
        except ConnectionClosedByServer:
            if time_limit_sec != float('inf'):
                raise
        except Exception:
            _logger.exception('Unexpected exception')
            raise
        _logger.info("Finish getting %.3f seconds of stream: %s", time_limit_sec, url)
        return client.get_stream()


def get_mjpeg_stream_info(url: str, auth_header: Optional[str] = None) -> _MJPEGStreamInfo:
    sample_duration_sec = 5
    _logger.info("Get %.3f seconds long sample of stream: %s", sample_duration_sec, url)
    with _RtspClient(url, auth_header=auth_header) as client:
        start_at = time.monotonic()
        try:
            client.receive_stream(sample_duration_sec)
        except ConnectionClosedByServer:
            stream_sample_duration = time.monotonic() - start_at
            if stream_sample_duration < 1:
                raise RuntimeError(
                    f"A stream sample is shorter than {sample_duration_sec}: "
                    f"{stream_sample_duration:.3f}. The result maybe incorrect.")
        _logger.info("Finish getting %.3f seconds of stream: %s", sample_duration_sec, url)
        return client.get_stream_info()


def get_multiple_rtsp_streams(
        url_list: Sequence[str],
        auth_header: Optional[str] = None) -> Sequence[Sequence[JpegImage]]:
    url_to_frames = {}
    url_count = len(url_list)
    started_at = time.monotonic()
    with ThreadPoolExecutor(max_workers=url_count) as executor:
        get_stream_fut_to_url = {
            executor.submit(get_rtsp_stream, url=url, auth_header=auth_header): url
            for url
            in url_list
            }
        for fut in as_completed(get_stream_fut_to_url):
            url = get_stream_fut_to_url[fut]
            frames = fut.result()
            url_to_frames[url] = frames
    finished_at = time.monotonic() - started_at
    _logger.debug("Getting %d streams took %.2f seconds", url_count, finished_at)
    return [url_to_frames[url] for url in url_list]
