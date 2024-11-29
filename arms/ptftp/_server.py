# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import logging
import os
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Iterator
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from threading import Thread
from typing import BinaryIO
from typing import Collection
from typing import Iterable
from typing import Optional
from typing import TypeVar

from arms.ptftp._endpoints_registry import EndpointsRegistry
from arms.ptftp._endpoints_registry import TFTPPathNotFound

_logger = logging.getLogger(__name__)


_max_datagram_size = (2 ** 16) - 1

_RRQ = 0x01
_DATA = 0x03
_ACK = 0x04
_ERROR = 0x05
_OACK = 0x06
_OACK_ERROR = 0x08

_opcode_length = 2


def bind_udp_socket(listen_ip: str, listen_port: int) -> socket.socket:
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))
    return sock


class TFTPEndpoint:

    def __init__(self, remote_ip: str, remote_port: int, local_socket: socket.socket):
        self._remote_ip = remote_ip
        self._remote_port = remote_port
        self._local_socket = local_socket

    def send_message(self, opcode: int, payload: bytes) -> None:
        opcode_encoded = opcode.to_bytes(_opcode_length, byteorder="big")
        message = opcode_encoded + payload
        message_length = len(message)
        sent = self._local_socket.sendto(message, (self._remote_ip, self._remote_port))
        _logger.debug("%s: Sent %s out of %s", self, sent, message_length)
        if sent != message_length:
            raise RuntimeError(f"Send size mismatch. Sent: {sent}, Expected: {message_length}")

    def receive_message(self, timeout: float) -> tuple[int, bytes]:
        for time_left in _time_until(timeout):
            self._local_socket.settimeout(time_left)
            try:
                datagram, (remote_ip, remote_port) = self._local_socket.recvfrom(_max_datagram_size)
            except TimeoutError:
                break
            if (remote_ip, remote_port) == (self._remote_ip, self._remote_port):
                opcode, payload = _parse_message(datagram)
                if opcode == _ERROR:
                    raise _EarlyTermination.from_bytes(payload)
                return opcode, payload
            _logger.warning(
                "%s: Ignore %s bytes from unknown source %s:%s",
                self, len(datagram), remote_ip, remote_port)
        raise _MessageWaitTimeout(f"{self} did not receive any suitable data after {timeout} sec")

    def close(self):
        self._local_socket.close()

    def __repr__(self):
        return f"<{self._remote_ip}:{self._remote_port}>"


class _MessageWaitTimeout(Exception):
    pass


class _TFTPError(Exception):

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self._code = code
        self._message = message

    def send_to(self, endpoint: TFTPEndpoint):
        errcode_encoded = self._code.to_bytes(2, byteorder="big")
        message_encoded = self._message.encode('ascii') + b'\x00'
        endpoint.send_message(_ERROR, errcode_encoded + message_encoded)


class _IllegalOperation(_TFTPError):

    def __init__(self, message: str):
        super().__init__(0x04, message)


class _TFTPFileNotFound(_TFTPError):

    def __init__(self, message: str):
        super().__init__(0x01, message)


class _AccessViolation(_TFTPError):

    def __init__(self, message: str):
        super().__init__(0x02, message)


class _UndefinedError(_TFTPError):

    def __init__(self, message: str):
        super().__init__(0x00, message)


class _EarlyTermination(Exception):

    @classmethod
    def from_bytes(cls, raw: bytes):
        code = int.from_bytes(raw[:2], byteorder="big")
        return cls(code, raw[2:-1].decode('ascii'))

    def __init__(self, code: int, message: str):
        super().__init__()
        self.code = code
        self.message = message


class _IndexedMessage(metaclass=ABCMeta):

    @abstractmethod
    def send(self, tftp_endpoint: TFTPEndpoint):
        pass

    @abstractmethod
    def is_acknowledged_by(self, index: int) -> bool:
        pass


class _Block(_IndexedMessage):

    def __init__(self, index: int, payload: bytes):
        self._index = index
        self._payload = payload

    def send(self, tftp_endpoint: TFTPEndpoint):
        block_number = self._index.to_bytes(2, byteorder="big")
        tftp_endpoint.send_message(_DATA, block_number + self._payload)

    def is_acknowledged_by(self, index: int) -> bool:
        return index == self._index

    def __repr__(self):
        return f"<Block {self._index}>"


class _OptionsAcknowledge(_IndexedMessage):

    @classmethod
    def gather(cls, *options: '_Option'):
        if requested_options := [option for option in options if option.is_requested()]:
            return cls(requested_options)
        raise _OptionsNotRequested()

    def __init__(self, requested_options: Collection['_Option']):
        self._requested_options = requested_options

    def send(self, tftp_endpoint: TFTPEndpoint):
        payload = bytearray()
        for key, value in self._options_pairs():
            payload.extend(key + b'\x00' + value + b'\x00')
        tftp_endpoint.send_message(_OACK, payload)

    def is_acknowledged_by(self, index: int) -> bool:
        return index == 0

    def _options_pairs(self) -> Iterable[tuple[bytes, bytes]]:
        return [option.encoded() for option in self._requested_options]

    def __repr__(self):
        options = ", ".join(
            f"{key.decode('ascii')}: {value.decode('ascii')}"
            for key, value in self._options_pairs())
        return f"<OACK {options}>"


class _OptionsNotRequested(Exception):
    pass


class _Option(metaclass=ABCMeta):

    @abstractmethod
    def encoded(self) -> tuple[bytes, bytes]:
        pass

    @abstractmethod
    def is_requested(self) -> bool:
        pass


class _AckTimeout(_Option):  # See: https://www.rfc-editor.org/rfc/rfc2349.html

    def __init__(self, options: Mapping[bytes, bytes], default: int):
        self._default = default
        self._requested: int
        raw = options.get(b'timeout')
        if raw is None:
            self._requested = 0
            return
        try:
            requested = int(raw)
        except ValueError:
            _logger.warning("Ignore unparseable timeout value %s", raw)
            self._requested = 0
            return
        if not 1 <= requested <= 255:
            _logger.warning("Ignore invalid timeout value %s", requested)
            self._requested = 0
        self._requested = requested

    def send_acknowledged(self, message: _IndexedMessage, tftp_endpoint: TFTPEndpoint):
        timeout = self._get_value()
        message.send(tftp_endpoint)
        for time_left in _time_until(timeout):
            try:
                opcode, index_raw = tftp_endpoint.receive_message(timeout=time_left)
            except _MessageWaitTimeout:
                break
            if opcode != _ACK:
                raise _IllegalOperation(f"Non-ACK request received: 0x{opcode:02x}")
            index = int.from_bytes(index_raw, byteorder="big")
            if message.is_acknowledged_by(index):
                return
            _logger.info("%s: ignored %s", message, index)
        raise _NotAcknowledged(f"{message} is not acknowledged after {timeout}")

    def is_requested(self):
        return self._requested > 0

    def encoded(self):
        return b'timeout', str(self._get_value()).encode('ascii')

    def _get_value(self) -> int:
        return self._requested if self._requested > 0 else self._default

    def __repr__(self):
        timeout = self._get_value()
        return f'<ACK timeout: {timeout}>'


class _NotAcknowledged(Exception):
    pass


class _BlockSize(_Option):  # See: https://datatracker.ietf.org/doc/html/rfc2348

    _default_size = 512  # See: https://datatracker.ietf.org/doc/html/rfc1350#section-2

    def __init__(self, options: Mapping[bytes, bytes]):
        requested_size_raw = options.get(b'blksize')
        self._requested_size: Optional[int]
        if requested_size_raw is None:
            self._requested_size = None
            return
        requested_size = int(requested_size_raw)
        if not 8 <= requested_size <= 65464:
            raise _UndefinedError(f"Unsupported block size {requested_size}")
        self._requested_size = requested_size

    def is_requested(self):
        return self._requested_size is not None

    def encoded(self):
        if self._requested_size is None:
            return b'blksize', str(self._default_size).encode('ascii')
        return b'blksize', str(self._requested_size).encode('ascii')

    def chunked(self, rd: BinaryIO) -> Iterator[bytes]:
        block_size = self._get_value()
        while True:
            block = rd.read(block_size)
            yield block
            if len(block) < block_size:
                return

    def _get_value(self) -> int:
        return self._default_size if self._requested_size is None else self._requested_size

    def __repr__(self):
        block_size = self._get_value()
        return f'<BlockSize: {block_size}>'


class _FileSize(_Option):  # https://www.rfc-editor.org/rfc/rfc2349.html

    def __init__(self, options: Mapping[bytes, bytes], rd: BinaryIO):
        self._size = _get_stream_size(rd) if options.get(b'tsize') is not None else -1

    def is_requested(self):
        return self._size > -1

    def encoded(self):
        if self._size > -1:
            return b'tsize', str(self._size).encode('ascii')
        return b'tsize', str(0).encode('ascii')

    def __repr__(self):
        return f'<FileSize: {self._size}>'


def _get_stream_size(fd: BinaryIO) -> int:
    current_position = fd.tell()
    try:
        return fd.seek(0, os.SEEK_END)
    finally:
        fd.seek(current_position, os.SEEK_SET)


class _Request(metaclass=ABCMeta):

    @abstractmethod
    def open_file(self, root_dir: Path) -> BinaryIO:
        pass

    @abstractmethod
    def execute(self, tftp_endpoint: TFTPEndpoint, fd: BinaryIO):
        pass


def _parse_request(datagram: bytes) -> _Request:
    opcode, payload = _parse_message(datagram)
    try:
        filename_raw, mode, *options_raw, _end = payload.split(b'\x00')
    except ValueError:
        raise _NonTFTPData()
    if opcode == _RRQ:
        if mode.lower() != b'octet':
            raise _IllegalOperation(f"Only 'octet' mode is supported while {mode!r} received")
        filename = filename_raw.decode('ascii')
        iter_options = iter(options_raw)
        options = {key.lower(): value for key, value in zip(iter_options, iter_options)}
        return _ReadRequest(filename, options)
    raise _IllegalOperation(f"Only Read requests are supported while 0x{opcode:02x} received")


def _parse_message(raw: bytes) -> tuple[int, bytes]:
    opcode = int.from_bytes(raw[:2], byteorder="big")
    payload = raw[2:]
    return opcode, payload


class _ReadRequest(_Request):

    def __init__(self, filename: str, options: Mapping[bytes, bytes]):
        self._filename = filename
        self._options = options

    def open_file(self, tftp_root_dir: Path) -> BinaryIO:
        file = tftp_root_dir / self._filename.lstrip("/")
        try:
            return file.open('rb')
        except FileNotFoundError:
            _logger.warning("%s: %s not exist", self, file)
            raise _TFTPFileNotFound(f"File {self._filename!r} not found")

    def execute(self, tftp_endpoint: TFTPEndpoint, rd: BinaryIO):
        _logger.info("%s: Sending %s to %s ...", self, self._filename, tftp_endpoint)
        start_at = time.monotonic()
        ack_timeout = _AckTimeout(self._options, default=1)
        block_size = _BlockSize(self._options)
        file_size = _FileSize(self._options, rd)
        reliable_stream = _ReliableStream(tftp_endpoint, ack_timeout, retry_count=5)
        try:
            options_acknowledge = _OptionsAcknowledge.gather(ack_timeout, block_size, file_size)
        except _OptionsNotRequested:
            _logger.debug("%s: No options are requested", self)
        else:
            _logger.info("%s: Acknowledge options: %s", self, options_acknowledge)
            reliable_stream.send_acknowledged(options_acknowledge)
        for block_num, file_chunk in _enumerate(
                block_size.chunked(rd), start_value=1, max_value=2 ** 16 - 1):
            reliable_stream.send_acknowledged(_Block(block_num, file_chunk))
        elapsed = time.monotonic() - start_at
        _logger.info(
            "%s: Successfully sent %s to %s. Elapsed: %03f sec",
            self, self._filename, tftp_endpoint, elapsed)

    def __repr__(self):
        return f'<ReadRequest: {self._filename!r}>'


_T = TypeVar('_T')


def _enumerate(
        iterator: Iterator[_T], start_value: int, max_value: int) -> Iterator[tuple[int, _T]]:
    # Clients and servers may wrap block numbers around. There is no clear restriction of that in
    # the TFTP RFC. This behaviour is observed in tftpd-hpa server and GRUB2 bootloader client.
    index = start_value
    wrap_after = max_value + 1
    for value in iterator:
        yield index, value
        index = (index + 1) % wrap_after


class _ReliableStream:

    def __init__(self, endpoint: TFTPEndpoint, ack_timeout: _AckTimeout, retry_count: int):
        self._endpoint = endpoint
        self._ack_timeout = ack_timeout
        self._retry_count = retry_count

    def send_acknowledged(self, message: _IndexedMessage):
        for attempt in range(1, self._retry_count + 1):
            try:
                return self._ack_timeout.send_acknowledged(message, self._endpoint)
            except _NotAcknowledged:
                _logger.warning(
                    "%s: Timeout while waiting ACK for %s. Attempt %s",
                    self._endpoint, message, attempt)
        raise _UndefinedError(f"{message} unacknowledged. Transmission interrupted.")


class TFTPServer:

    def __init__(self, server_sock: socket.socket, endpoints_registry: EndpointsRegistry):
        self._socket = server_sock
        self._endpoints_registry = endpoints_registry
        self._active_sessions: dict[tuple[str, int], Thread] = {}
        self._listen_ip, self._listen_port = server_sock.getsockname()

    def serve_forever(self, max_sessions: int):
        loop_turn_time = 1
        while True:
            try:
                request, remote_ip, remote_port = self._get_request(timeout=loop_turn_time)
            except _RequestNotReceived:
                self._pop_finished()
                _logger.debug("%s: periodic maintenance performed", self)
                continue
            client_socket = bind_udp_socket(self._listen_ip, 0)
            tftp_endpoint = TFTPEndpoint(remote_ip, remote_port, client_socket)
            self._pop_finished()
            if len(self._active_sessions) > max_sessions:
                _logger.error("%s: Can't open session due to lack of free client slots", self)
                _UndefinedError("Not enough resources").send_to(tftp_endpoint)
                tftp_endpoint.close()
                continue
            try:
                fd = self._open_fd(request, remote_ip)
            except _TFTPError as err:
                _logger.warning(
                    "%s: Can't fulfil %s because %s", self, request, str(err))
                err.send_to(tftp_endpoint)
                tftp_endpoint.close()
                continue
            thread = Thread(
                target=_client_session,
                args=(request, fd, tftp_endpoint),
                name=f"{tftp_endpoint}:{request}",
                )
            self._active_sessions[(remote_ip, remote_port)] = thread
            thread.start()

    def _get_request(self, timeout: int) -> tuple[_Request, str, int]:
        for time_left in _time_until(timeout):
            self._socket.settimeout(time_left)
            try:
                datagram, (remote_ip, remote_port) = self._socket.recvfrom(_max_datagram_size)
            except TimeoutError:
                break
            try:
                request = _parse_request(datagram)
            except _TFTPError as err:
                _logger.warning("%s: Request cannot be executed due to: %s", self, str(err))
                server_temporary_endpoint = TFTPEndpoint(remote_ip, remote_port, self._socket)
                err.send_to(server_temporary_endpoint)
                continue
            except _NonTFTPData:
                _logger.warning(
                    "%s: Ignore Non-TFTP %s bytes from %s:%s",
                    self, len(datagram), remote_ip, remote_port)
                continue
            except Exception as err:
                _logger.warning(
                    "%s: Ignore %s bytes from %s:%s",
                    self, len(datagram), remote_ip, remote_port, exc_info=err)
                continue
            if (remote_ip, remote_port) in self._active_sessions:
                _logger.warning(
                    "%s: Ignore %s from already active %s:%s",
                    self, request, remote_ip, remote_port)
                continue
            return request, remote_ip, remote_port
        raise _RequestNotReceived(f"Did not receive any TFTP requests after {timeout}")

    def _open_fd(self, request: _Request, remote_ip: str) -> BinaryIO:
        tftp_root = self._find_root(remote_ip)
        return request.open_file(tftp_root)

    def _find_root(self, remote_ip: str) -> Path:
        try:
            explicit_tftp_root = self._endpoints_registry.find_root_path(remote_ip)
        except TFTPPathNotFound:
            _logger.info("%s: Can't find explicit TFTP path", self)
            try:
                default_tftp_root = self._endpoints_registry.find_root_path('0.0.0.0')
            except TFTPPathNotFound:
                raise _AccessViolation(f"Server is not configured to serve {remote_ip}")
            _logger.info("%s: Use default TFTP path %s", self, default_tftp_root)
            return default_tftp_root
        _logger.info("%s: Found explicit TFTP path %s", self, explicit_tftp_root)
        return explicit_tftp_root

    def _pop_finished(self):
        for remote_address, thread in list(self._active_sessions.items()):
            if not thread.is_alive():
                thread.join()
                _logger.debug(f"{thread} is joined")
                self._active_sessions.pop(remote_address)

    def wait_requests_done(self):
        for remote_address, thread in list(self._active_sessions.items()):
            thread.join(timeout=30)
            if not thread.is_alive():
                _logger.debug(f"{thread} is joined at close")
                self._active_sessions.pop(remote_address)
        if self._active_sessions:
            raise RuntimeError(f"{self._active_sessions} are still active")

    def __repr__(self):
        return f'<Server {self._listen_ip}:{self._listen_port}>'


class _RequestNotReceived(Exception):
    pass


class _NonTFTPData(Exception):
    pass


def _client_session(request: _Request, fd: BinaryIO, tftp_endpoint: TFTPEndpoint):
    with closing(tftp_endpoint), closing(fd):
        try:
            request.execute(tftp_endpoint, fd)
        except _EarlyTermination as err:
            _logger.warning("%s: Client error: [0x%02d] %r", request, err.code, err.message)
        except _TFTPError as err:
            _logger.warning("%s: A TFTP error while serving: %s", request, err)
            err.send_to(tftp_endpoint)
        except OSError as err:
            if err.errno == errno.EBADF:
                _logger.info("%s: Session is interrupted due to the local socket close", request)
                return
            raise
        except Exception:
            _logger.exception("%s: An unexpected exception while serving", request)
            raise


def _time_until(timeout: float) -> Iterator[float]:
    time_left = timeout
    timeout_at = time.monotonic() + timeout
    while True:
        yield time_left
        time_left = timeout_at - time.monotonic()
        if time_left < 0:
            break
