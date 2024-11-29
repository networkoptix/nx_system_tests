# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""RTSP camera server.

Designed according to:
RFC 2326: https://tools.ietf.org/html/rfc2326  (RTSP)
RFC 1889: https://tools.ietf.org/html/rfc1889  (RTP)
Only basic features are implemented.
"""
import logging
import struct
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from doubles.software_cameras._camera_server import CameraServer
from doubles.software_cameras._camera_server import Connection
from doubles.software_cameras._camera_server import NoHeadline
from doubles.software_cameras._camera_server import PeerDisconnected
from doubles.software_cameras._camera_server import rate_hz
from doubles.software_cameras._h264 import H264Stream
from doubles.software_cameras._motion_jpeg import MotionJpegStream

_logger = logging.getLogger(__name__)


class _UnknownRtspMethod(Exception):
    pass


class _RtspConnection(Connection, metaclass=ABCMeta):

    def __init__(
            self,
            sock,
            addr,
            user: Optional[str] = None,
            password: Optional[str] = None):
        super().__init__(sock, addr, user, password)
        self._rtp_sequence_number = 0
        self._session_id = self._addr[1]  # Arbitrary, but unique, so client port can be used
        self._rtp_channel: bytes  # Initialized after SETUP method from client
        # RTCP protocol is actually unused in current implementation.
        # This variable is only needed to respond client with correct SETUP message.
        self._rtcp_channel: bytes  # Initialized after SETUP method from client

    def _respond_not_allowed(self):
        self._file.write(
            b'HTTP/1.0 405 Method Not Allowed\r\n'
            b'\r\n')
        self._file.flush()

    def _respond_options(self, cseq):
        # All required methods are supported: https://tools.ietf.org/html/rfc2326#page-29
        # Recommended method DESCRIBE is supported.
        supported_methods = b'DESCRIBE, SETUP, TEARDOWN, PLAY, OPTIONS'
        self._file.write(
            b'RTSP/1.0 200 OK\r\n'
            b'CSeq: %s\r\n'
            b'Public: %s\r\n'
            b'\r\n'
            % (
                cseq,
                supported_methods,
                ))
        self._file.flush()

    def _respond_unauthorized(self, cseq):
        self._file.write(
            b'RTSP/1.0 401 Unauthorized\r\n'
            b'CSeq: %s\r\n'
            b'WWW-Authenticate: Basic realm="%s", charset="UTF-8\r\n'
            b'\r\n'
            % (
                cseq,
                self.realm.encode('ascii'),
                ))
        self._file.flush()

    def _respond_describe(self, cseq):
        now = datetime.utcnow()
        timestamp = int(now.timestamp() * 10**6)
        date = now.strftime('%d %b %Y %T UTC').encode('ascii')
        # SDP format is used: https://www.rfc-editor.org/rfc/rfc2327
        # Only mandatory attributes specified
        # Using timestamp as session id and version is suggested in RFC
        sdp_headers = (
                b'v=0\r\n'  # SDP version
                b'o=- %(session_id)d %(version)d IN IP4 0.0.0.0\r\n'  # Owner info
                b's=NX FT RTSP Session\r\n'  # Session name
                b't=0 0\r\n'  # Start/stop media ts (may be zero)
                b'm=video 0 RTP/AVP %(payload_type)d\r\n'
                b'a=rtpmap:%(rtpmap)s\r\n'
                % {
                    b'session_id': timestamp,
                    b'version': timestamp,
                    b'payload_type': self._video_stream.payload_type,
                    b'rtpmap': self._video_stream.rtpmap,
                    })
        self._file.write(
            b'RTSP/1.0 200 OK\r\n'
            b'CSeq: %s\r\n'
            b'Date: %s\r\n'
            b'Session: %d;timeout=60\r\n'
            b'Content-type: application/sdp\r\n'
            b'Content-length: %d\r\n'
            b'\r\n'
            % (
                cseq,
                date,
                self._session_id,
                len(sdp_headers),
                ))
        self._file.write(sdp_headers)
        self._file.flush()

    def _respond_setup(self, cseq):
        self._file.write(
            b'RTSP/1.0 200 OK\r\n'
            b'CSeq: %s\r\n'
            b'Transport: RTP/AVP/TCP;unicast;interleaved=%s-%s\r\n'
            b'Session: %d\r\n'
            b'\r\n'
            % (
                cseq,
                self._rtp_channel,
                self._rtcp_channel,
                self._session_id,
                ))
        self._file.flush()

    def _respond_ok(self, cseq):
        self._file.write(
            b'RTSP/1.0 200 OK\r\n'
            b'CSeq: %s\r\n'
            b'\r\n'
            % cseq)
        self._file.flush()

    def _respond_unsupported_transport(self, cseq):
        self._file.write(
            b'RTSP/1.0 461 Client error\r\n'
            b'CSeq: %s\r\n'
            b'\r\n'
            % cseq)
        self._file.flush()

    def _rtsp_interleaved_frame(self, data_length):
        return struct.pack(
            '>cBH',
            b'$',  # This is called 'magic character'
            int(self._rtp_channel),
            data_length)

    @abstractmethod
    def _try_update_rtp_timestamp(self, pts_ms):
        pass

    @abstractmethod
    def _rtp_marker_required(self):
        pass

    def _make_rtp_header(self, pts_ms):
        rtp_version = 2
        has_end_of_image_flag = self._rtp_marker_required()
        if self._rtp_sequence_number < 65535:
            self._rtp_sequence_number += 1
        else:
            self._rtp_sequence_number = 1
        timestamp = self._try_update_rtp_timestamp(pts_ms)
        ssrc = self._addr[1]  # Arbitrary, but unique, so client port can be used
        return struct.pack(
            '>BBHII',  # noqa SpellCheckingInspection
            rtp_version << 6,  # rightmost 6 bits are unused flags and are set to 0
            (int(has_end_of_image_flag) << 7) + self._video_stream.payload_type,
            self._rtp_sequence_number,
            timestamp,
            ssrc)

    @abstractmethod
    def _get_next_frame(self):
        pass

    def _encapsulate_frame(self, encoded_frame, pts_ms) -> bytes:
        rtp_header = self._make_rtp_header(pts_ms)
        rtp_payload = rtp_header + encoded_frame
        interleaved_frame = self._rtsp_interleaved_frame(len(rtp_payload))
        return interleaved_frame + rtp_payload

    @abstractmethod
    def _save_current_frame(self):
        pass

    @abstractmethod
    def _ready_to_send_frame(self):
        pass

    @abstractmethod
    def _try_increase_pts(self):
        pass

    @abstractmethod
    def _close_stream(self):
        pass

    def handle(self):
        try:
            [request, version] = self._read_request()
        except NoHeadline:
            _logger.info("Not a RTSP request; Probably RTCP; Skipping data")
            return 'continue'
        except PeerDisconnected:
            return 'disconnect'
        if request.method == b'GET':
            _logger.info("Unsupported 'GET' request; respond '405 Not Allowed'")
            self._respond_not_allowed()
            self.close()
            return 'disconnect'
        self.path = request.selector.rstrip('/')  # VLC can add '/' in the end of the URL for some reason
        cseq = request.headers[b'Cseq']
        if version != b'RTSP/1.0':
            raise NotImplementedError("Only RTSP v1.0 supported")
        try:
            auth_header = request.headers[b'Authorization']
        except KeyError:
            if self.auth_header is not None:
                _logger.info("Camera requires authorization; respond unauthorized")
                self._respond_unauthorized(cseq)
                return 'continue'
        else:
            if self.auth_header is None:
                _logger.warning("Request with auth header, but auth unspecified on camera server")
            elif auth_header != self.auth_header:
                raise RuntimeError("Camera authorization mismatch")
        if request.method == b'OPTIONS':
            self._respond_options(cseq)
            return 'continue'
        if request.method == b'DESCRIBE':
            self._respond_describe(cseq)
            return 'continue'
        if request.method == b'SETUP':
            transport = request.headers[b'Transport']
            if b'interleaved=' not in transport:
                _logger.info("RTSP camera server only supports 'TCP interleaved' transport")
                self._respond_unsupported_transport(cseq)
            else:
                [_, channels] = transport.split(b'interleaved=')
                [self._rtp_channel, self._rtcp_channel] = channels.split(b'-')
                self._respond_setup(cseq)
            return 'continue'
        if request.method == b'PLAY':
            self._init_stream()
            self._respond_ok(cseq)
            return 'stream'
        if request.method == b'TEARDOWN':
            try:
                self._respond_ok(cseq)
            except ConnectionError:
                _logger.error("%r: Client closed the connection after sending TEARDOWN", self)
            self._close_stream()
            self.close()
            return 'disconnect'
        else:
            raise _UnknownRtspMethod(f"Got unknown RTSP method: {request.method}")


class _MjpegRtspConnection(_RtspConnection):

    def __init__(self, sock, addr, video_source: MotionJpegStream, user, password):
        self._video_stream = video_source
        super().__init__(sock, addr, user, password)

    def _try_update_rtp_timestamp(self, pts_ms):
        return int(pts_ms / 1000 * rate_hz) % 2**32

    def _rtp_marker_required(self):
        return True

    def _get_next_frame(self):
        return self._video_stream.get_frame()

    def _save_current_frame(self):
        self.sent_frames.append(self._video_stream.current_frame)

    def _ready_to_send_frame(self):
        return self._pts_ticks <= self._now_ticks()

    def _try_increase_pts(self):
        self._pts_ticks += rate_hz // self._video_stream.fps

    def _close_stream(self):
        pass


class _H264RtspConnection(_RtspConnection):

    def __init__(self, sock, addr, source_video_file, fps, user, password):
        self._video_stream = H264Stream(source_video_file, fps)
        super().__init__(sock, addr, user, password)
        self._current_nal_unit = self._video_stream.get_next_frame()

    def _get_next_frame(self):
        return self._current_nal_unit.raw

    def _try_update_rtp_timestamp(self, pts_ms):
        if self._current_nal_unit.requires_timestamp_update:
            self._timestamp = int(pts_ms / 1000 * rate_hz) % 2**32
        try:
            return self._timestamp
        except AttributeError:
            self._timestamp = int(pts_ms / 1000 * rate_hz) % 2**32
            return self._timestamp

    def _rtp_marker_required(self):
        return self._current_nal_unit.requires_rtp_marker

    def _save_current_frame(self):
        if self._current_nal_unit.requires_timestamp_update:
            self.sent_frames.append(self._current_nal_unit.raw)

    def _ready_to_send_frame(self):
        if self._frame_was_sent:
            self._current_nal_unit = self._video_stream.get_next_frame()
        pts_delay = self._pts_ticks - self._now_ticks()
        _logger.debug(
            f"{self}: Current frame type: %d; PTS delay: %d",
            self._current_nal_unit.type, pts_delay)
        is_not_first_fragment = self._current_nal_unit.is_fragment and not self._current_nal_unit.is_first_fragment
        return self._current_nal_unit.is_service_data or is_not_first_fragment or pts_delay <= 0

    def _try_increase_pts(self):
        if self._current_nal_unit.requires_timestamp_update:
            self._pts_ticks += rate_hz // self._video_stream.fps

    def _close_stream(self):
        self._video_stream.close()


class MjpegRtspCameraServer(CameraServer):

    protocol = 'rtsp'
    codec = 'mjpeg'

    def __init__(
            self,
            address='0.0.0.0',
            video_source: Optional[MotionJpegStream] = None,
            port=0,
            user=None,
            password=None,
            ):
        super().__init__(address, port, user, password)
        if video_source is not None:
            self.video_source = video_source
        else:
            frame_size = (640, 320)
            self.video_source = MotionJpegStream(frame_size)

    def _get_connection(self, new_sock, addr):
        return _MjpegRtspConnection(new_sock, addr, self.video_source, self._user, self._password)


class H264RtspCameraServer(CameraServer):

    protocol = 'rtsp'
    codec = 'h264'

    def __init__(
            self,
            source_video_file: Path,
            fps=30,
            address='0.0.0.0',
            port=0,
            user=None,
            password=None,
            ):
        super().__init__(address, port, user, password)
        self._source_video_file = source_video_file
        self._fps = fps

    def _get_connection(self, new_sock, addr):
        return _H264RtspConnection(
            new_sock, addr, self._source_video_file, self._fps, self._user, self._password)
