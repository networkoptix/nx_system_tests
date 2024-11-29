# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
import threading
import time
from abc import ABCMeta
from abc import abstractmethod
from base64 import b64encode
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import contextmanager
from itertools import chain
from selectors import DefaultSelector
from selectors import EVENT_READ
from typing import List
from typing import Literal
from typing import Optional
from typing import Sequence
from typing import Tuple
from urllib.request import Request

from doubles.software_cameras._jpeg import JpegImage

_logger = logging.getLogger(__name__)

rate_hz = 90000  # Ticks per second.


class PeerDisconnected(Exception):
    pass


class NoHeadline(Exception):
    pass


class Connection(metaclass=ABCMeta):

    fps: int

    def __init__(
            self,
            sock,
            addr,
            user: Optional[str] = None,
            password: Optional[str] = None):
        self._sock = sock
        # .recv() is used with select/poll and must never block.
        # .send() shouldn't fill the buffer, or a timeout error will show it.
        self._sock.setblocking(False)
        self._addr = addr
        self._file = self._sock.makefile('rwb')
        if user is None and password is None:
            self.auth_header = None
        elif user is not None and password is not None:
            auth_line = user.encode() + b':' + password.encode()
            self.auth_header = b'Basic ' + b64encode(auth_line)
        self.user = user
        self.password = password
        self.realm = "DoesNotMatter"
        self._frame_was_sent = False
        self._pts_ticks: int  # Initialized later
        self.sent_frames: List[bytes]  # Initialized later
        self.path: str  # Initialized later

    def __repr__(self):
        [host, port] = self._addr
        if host == '127.0.0.1':
            host = ''
        try:
            path = self.path
        except AttributeError:
            return '<_Client {}:{}>'.format(host, port)
        else:
            return '<_Client {}:{} {}>'.format(host, port, path)

    def close(self):
        try:
            self._file.close()
        except (BrokenPipeError, ConnectionAbortedError):  # Socket can be closed from the other side
            pass
        except ConnectionResetError as e:
            _logger.debug("%r: close: RST from peer (crash?): %s", self, e)
        finally:
            self._sock.close()

    def fileno(self):
        return self._sock.fileno()

    def _read_request_line(self):
        try:
            headline = self._file.readline(200)
        except ConnectionResetError:
            # RST from the peer on Linux.
            raise PeerDisconnected("Connection reset by the peer")
        except ConnectionAbortedError:
            # RST from the peer on Windows.
            raise PeerDisconnected("Connection reset by the peer")
        except OSError as e:
            if isinstance(e, TimeoutError):
                no_bytes_available = True
            else:
                expected_message = (
                    "read() should have returned a bytes object, "
                    "not 'NoneType'")
                actual_message = e.args[0]
                if actual_message == expected_message:
                    no_bytes_available = True
                else:
                    no_bytes_available = False
            if no_bytes_available:
                # If no bytes available on a non-blocking socket, readinto()
                # returns None, and readline() raises an OSError on that.
                # Any timeout forces causes a TimeoutError.
                # Cases where an expected data (e.g. HTTP headers) comes
                # in parts and some part is delayed, haven't been seen yet.
                # That's why the connection is terminated.
                raise NoHeadline(
                    "No headline: cannot read the first line, "
                    "the protocol seems to be binary")
            raise
        if not headline:
            raise PeerDisconnected("Connection closed by the peer")
        if headline.startswith(b'<'):
            raise PeerDisconnected(
                "Unsupported protocol: it seems to be raw XML over TCP, "
                "maybe it's a check for SOAP/ONVIF")
        try:
            [method, url, version] = headline.split()
        except ValueError:
            raise PeerDisconnected(
                "Unsupported protocol: cannot parse the status line: "
                "cannot split it into three parts (method, url and version): "
                f"{headline}")
        _logger.debug("%r: Status line: %r", self, headline)
        return method, url, version

    def _read_headers(self):
        headers = {}
        while True:
            header = self._file.readline().rstrip(b'\r\n')
            _logger.debug("%r: Header: %r", self, header)
            if header == b'':
                break
            [name, value] = header.split(b': ', 1)
            headers[name] = value
        return headers

    def _read_request(self):
        [method, url, version] = self._read_request_line()
        headers = self._read_headers()
        # RTSP camera can also receive HTTP requests, so it must be able to parse them.
        # HTTP requests may only contain path instead of full_url.
        if url.startswith(b'/'):
            [local_ip, local_port] = self._sock.getsockname()
            url_str = f'http://{local_ip}:{local_port}{url.decode()}'
        else:
            url_str = url.decode()
        return Request(url=url_str, headers=headers, method=method), version

    @abstractmethod
    def handle(self) -> Literal['stream', 'continue', 'disconnect']:
        pass

    @abstractmethod
    def _get_next_frame(self) -> bytes:
        pass

    def _now_ticks(self):
        return int(time.monotonic() * rate_hz)

    def _init_stream(self):
        _period_ticks = rate_hz // self._video_stream.fps
        self._pts_ticks = self._now_ticks() // _period_ticks * _period_ticks
        self.sent_frames = []

    @abstractmethod
    def _encapsulate_frame(self, encoded_frame: bytes, pts_ms: int) -> bytes:
        pass

    @abstractmethod
    def _save_current_frame(self):
        pass

    @abstractmethod
    def _ready_to_send_frame(self):
        pass

    @abstractmethod
    def _try_increase_pts(self):
        pass

    def stream(self) -> Literal['disconnect', 'continue']:
        if not self._ready_to_send_frame():
            self._frame_was_sent = False
            return 'continue'
        self._try_increase_pts()
        pts_ms = self._pts_ticks * 1000 // rate_hz
        encoded_frame = self._get_next_frame()
        encapsulated_frame = self._encapsulate_frame(encoded_frame, pts_ms)
        _logger.debug(
            "%r: Send frame, PTS %d ms, size %d B",
            self, pts_ms, len(encapsulated_frame))
        try:
            self._file.write(encapsulated_frame)
            self._file.flush()
        except (
                ConnectionResetError,
                ConnectionAbortedError,  # Seen only on Windows.
                BrokenPipeError,
                ) as e:
            streamed_ms = self.get_streamed_seconds() * 1000
            _logger.info(
                "%r: error after %d ms (%d frames): %r",
                self, streamed_ms, len(self.sent_frames), e)
            self.close()
            return 'disconnect'
        except BlockingIOError:
            _logger.warning("%r: Outbound buffer is overloaded; Wait for clearing", self)
            self._frame_was_sent = False
            return 'continue'
        self._save_current_frame()
        self._frame_was_sent = True
        return 'continue'

    def get_streamed_seconds(self):
        return len(self.sent_frames) / self._video_stream.fps


class CameraServer(metaclass=ABCMeta):

    protocol: str
    codec: str

    def __init__(self, address='0.0.0.0', port=0, user=None, password=None):
        self._user = user
        self._password = password
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # .accept() is used with select/poll and never blocks.
        self._server_sock.setblocking(False)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((address, port))
        self._server_sock.listen(100)
        [self._host, self.port] = self._server_sock.getsockname()
        self._poll = DefaultSelector()
        self._poll.register(self._server_sock, EVENT_READ)
        self._stream_to: List[Connection] = []
        self._disconnected_clients: List[Connection] = []
        self._stop_event = threading.Event()
        _logger.info("Start camera server at %s:%d", self._host, self.port)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def disconnect_all(self):
        _logger.info("Disconnect all clients with FIN")
        started_at = time.monotonic()
        while self._stream_to:
            _logger.debug("Open sockets: %r", self._stream_to)
            sock = self._stream_to.pop()
            sock.close()
            self._disconnected_clients.append(sock)
            if time.monotonic() - started_at > 30:
                raise RuntimeError("Couldn't close all sockets after timeout")
        _logger.info("Unregister file objects")
        for selector_key in list(self._poll.get_map().values()):
            if selector_key.fileobj is self._server_sock:
                continue
            _logger.debug("Unregister file object: %r", selector_key.fileobj)
            self._poll.unregister(selector_key.fileobj)
            selector_key.fileobj.close()

    def close(self):
        self.disconnect_all()
        _logger.info("Stop camera server at %s:%d", self._host, self.port)
        self._poll.unregister(self._server_sock)
        self._server_sock.close()
        self._poll.close()

    def get_frames(self, path_list: Sequence[str]) -> Sequence[Sequence[JpegImage]]:
        frames = {path: [] for path in path_list}
        for client in chain(self._disconnected_clients, self._stream_to):
            if client.path in path_list:
                frames[client.path].extend(client.sent_frames)
        return [frames[path] for path in path_list]

    def get_durations_sec(self, path_list):
        seconds = {path: 0 for path in path_list}
        for client in chain(self._disconnected_clients, self._stream_to):
            # After force disconnect mediaserver is trying to reconnect to
            # the camera and this leads to clients from previous record_from_cameras
            # calls appear in _stream_to in the next call.
            if client.path in path_list:
                seconds[client.path] += client.get_streamed_seconds()
        return [seconds[path] for path in path_list]

    @abstractmethod
    def _get_connection(self, new_sock: socket.socket, addr: Tuple[str, int]) -> Connection:
        pass

    def _accept_new_connection(self):
        [new_sock, addr] = self._server_sock.accept()
        new_connection = self._get_connection(new_sock, addr)
        _logger.debug("New connection: %r", new_connection)
        self._poll.register(new_connection, EVENT_READ)

    def _handle_connection(self, connection: Connection):
        transition = connection.handle()
        if transition == 'disconnect':
            _logger.debug("%r: Unregister", connection)
            self._poll.unregister(connection)
            try:
                self._stream_to.remove(connection)
            except ValueError:
                _logger.debug("%r: Disconnected before requesting stream", connection)
            else:
                connection.close()
                self._disconnected_clients.append(connection)
        elif transition == 'stream':
            if connection not in self._stream_to:
                _logger.debug("%r: Start streaming", connection)
                self._stream_to.append(connection)
            else:
                _logger.debug("%r: Stream already requested", connection)
        else:
            _logger.debug("%r: Continue handling", connection)

    def serve(self, time_limit_sec=float('inf'), break_on_silence_sec=float('inf')):
        # TODO: Limit time without a connection (idle time).
        if time_limit_sec == float('inf'):
            _logger.info("Serve: no time limit")
        else:
            _logger.info("Serve: time limit: %.1f sec", time_limit_sec)
        silence_since = time.monotonic()
        started_at = time.monotonic()
        while True:  # At least one iteration should occur.
            if self._stream_to:
                selector_result = self._poll.select(0.001)
            else:
                # If nothing is happening, don't poll/select frequently
                # and limit how often it's reported that nothing is happening.
                selector_result = self._poll.select(1)
                if selector_result:
                    silence_since = time.monotonic()
                elif time.monotonic() - silence_since >= break_on_silence_sec:
                    _logger.info(
                        "Break: silence for %.1f sec",
                        time.monotonic() - silence_since)
                    return
                else:
                    _logger.info(
                        "No streaming, no incoming requests for %.1f sec",
                        time.monotonic() - silence_since)
            for [selector_key, _] in selector_result:
                if selector_key.fileobj is self._server_sock:
                    self._accept_new_connection()
                    continue
                self._handle_connection(selector_key.fileobj)
            for connection in self._stream_to:
                transition = connection.stream()
                if transition == 'disconnect':
                    self._poll.unregister(connection)
                    self._stream_to.remove(connection)
                    self._disconnected_clients.append(connection)
            if time.monotonic() - started_at > time_limit_sec:
                _logger.info("Break: time limit exceeded")
                return
            if self._stop_event.is_set():
                return

    @contextmanager
    def async_serve(self):
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='thread_camera_server') as executor:
            serve_fut = executor.submit(self.serve)
            try:
                yield
            finally:
                self._stop_event.set()
                # More than enough to complete an iteration in .serve().
                serve_fut.result(timeout=2)
                self._stop_event.clear()

    def wait_until_all_disconnect(self, timeout_sec):
        silence_sec = 2
        _logger.info(
            "Clients must disconnect and not reconnect for %.1f sec "
            "with %.1f sec timeout",
            silence_sec, timeout_sec)
        serve_started_at = time.monotonic()
        self.serve(time_limit_sec=timeout_sec, break_on_silence_sec=silence_sec)
        serve_sec = time.monotonic() - serve_started_at
        if self._stream_to:
            raise RuntimeError(
                "Clients are still connected "
                f"{serve_sec} sec after recording was stopped: "
                f"{self._stream_to}")
        _logger.info(
            "Clients disconnected "
            "%.1f sec after recording was stopped",
            serve_sec - silence_sec)

    def clean_up(self):
        self._disconnected_clients.clear()
