# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import socket
from typing import Literal
from typing import Optional
from typing import Tuple
from urllib.request import Request

from doubles.software_cameras._camera_server import CameraServer
from doubles.software_cameras._camera_server import Connection
from doubles.software_cameras._camera_server import NoHeadline
from doubles.software_cameras._camera_server import PeerDisconnected
from doubles.software_cameras._camera_server import rate_hz
from doubles.software_cameras._motion_jpeg import JPEGSequence

_logger = logging.getLogger(__name__)

_boundary = b'ffserver'
_frame_cache = {}


class _MultiPartJpegConnection(Connection):

    def __init__(
            self,
            sock: socket.socket,
            addr: Tuple[str, int],
            video_source: JPEGSequence,
            user: Optional[str] = None,
            password: Optional[str] = None):
        self._video_stream = video_source
        super().__init__(sock, addr, user, password)
        self._buffer_size = self._sock.getsockopt(
            socket.SOL_SOCKET, socket.SO_SNDBUF)

    def _respond_right_away(self, status_code, reason_phrase):
        self._file.write(
            b'HTTP/1.1 %(status_code)d %(reason_phrase)s\r\n'
            b'Connection: Keep-Alive\r\n'
            b'Cache-Control: no-cache\r\n'
            b'Content-Length: %(reason_phrase_len)d\r\n'
            b'\r\n'
            b'%(reason_phrase)s'
            % {
                b'status_code': status_code,
                b'reason_phrase': reason_phrase.encode('ascii'),
                b'reason_phrase_len': len(reason_phrase.encode('ascii')),
                })
        self._file.flush()

    def _respond_unauthorized(self):
        _logger.info("Respond 401 Unauthorized")
        self._file.write(
            b'HTTP/1.1 401 Unauthorized\r\n'
            b'WWW-Authenticate: Basic realm="%s", charset="UTF-8"\r\n'
            b'Content-Length: 0\r\n'
            b'\r\n'
            % self.realm.encode('ascii'))
        self._file.flush()

    def _start_multipart(self):
        self._file.write(
            b'HTTP/1.1 200 OK\r\n'
            b'Connection: Keep-Alive\r\n'
            b'Content-Type: multipart/x-mixed-replace;boundary=%s\r\n'
            b'Cache-Control: no-cache\r\n'
            b'\r\n'
            % _boundary)
        self._file.flush()

    def handle(self):
        _logger.debug("%r: Handle", self)
        try:
            [request, _] = self._read_request()
        except (PeerDisconnected, NoHeadline) as e:
            _logger.info("%r: Disconnected after request: %s", self, e.args[0])
            return 'disconnect'
        _logger.debug("%r: Request to %s", self, request.selector)
        auth_received = request.headers.get(b'Authorization')
        if self.auth_header is None:
            _logger.info("%r: No authentication: %s", self, request.selector)
        elif self.auth_header == auth_received:
            _logger.info("%r: Authenticated: %s", self, request.selector)
        else:
            _logger.info(
                "%r: Expected auth %s != received auth %s: %s",
                self, self.auth_header, auth_received, request.selector)
            self._respond_unauthorized()
            return 'disconnect'
        return self._handle_authenticated(request)

    def _handle_authenticated(
            self,
            request: Request) -> Literal['stream', 'continue', 'disconnect']:
        path = request.selector
        assert path.startswith('/')
        _, extension = os.path.splitext(path[1:])
        if extension == '.mjpeg':
            self.path = path
            _logger.info("%r: Multipart JPEG request: %r", self, path)
            try:
                self._start_multipart()
            except (ConnectionResetError, BrokenPipeError) as e:
                _logger.warning("%r: %s when starting %s", self, e, path)
                return 'disconnect'
            self._init_stream()
            return 'stream'
        else:
            _logger.info("%r: Unsupported request: %s", self, path)
            try:
                self._respond_right_away(405, 'Not Found')
            except (ConnectionResetError, BrokenPipeError) as e:
                _logger.warning("%r: %s when responding to %s", self, e, path)
                return 'disconnect'
            return 'continue'

    def _get_next_frame(self):
        return self._video_stream.get_frame().raw

    def _encapsulate_frame(self, encoded_frame, pts_ms):
        # All PTSes seen in traffic captures were multiples of 1000.
        headers = (
            b'Content-Type: image/jpeg\r\n'
            b'X-Content-Timestamp: %(ts)d000\r\n'
            b'Content-Length: %(length)d\r\n'
            b'\r\n'
            % {b'ts': pts_ms, b'length': len(encoded_frame)}
            )
        encapsulated_frame = (
            b'--%s\r\n'
            b'%s'
            b'%s\r\n'
            % (_boundary, headers, encoded_frame)
            )
        self._adjust_buffer_size(len(encapsulated_frame))
        return encapsulated_frame

    def _save_current_frame(self):
        self.sent_frames.append(self._video_stream.current_frame)

    def _ready_to_send_frame(self):
        return self._pts_ticks <= self._now_ticks()

    def _try_increase_pts(self):
        self._pts_ticks += rate_hz // self._video_stream.fps

    def _adjust_buffer_size(self, reference_frame_size):
        # It's also assumed that TCP send buffer always has free
        # space in it; given that send buffer is large enough, test
        # wouldn't have much sense if sending were congested.
        buffer_len_sec = 2
        new_buffer_size = int(buffer_len_sec * self._video_stream.fps * reference_frame_size)
        if new_buffer_size <= self._buffer_size:
            return
        self._sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_SNDBUF,
            new_buffer_size)
        self._buffer_size = new_buffer_size


class MultiPartJpegCameraServer(CameraServer):

    protocol = 'http'
    codec = 'mjpeg'

    def __init__(
            self,
            address='0.0.0.0',
            port=0,
            video_source: Optional[JPEGSequence] = None,
            user=None,
            password=None,
            ):
        super().__init__(address, port, user, password)
        if video_source is not None:
            self.video_source = video_source
        else:
            frame_size = (640, 320)
            self.video_source = JPEGSequence(frame_size)

    def _get_connection(self, new_sock, addr):
        return _MultiPartJpegConnection(
            new_sock, addr, self.video_source, self._user, self._password)
