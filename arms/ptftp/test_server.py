# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import logging
import socket
import tempfile
import time
import unittest
from collections import deque
from itertools import cycle
from pathlib import Path
from threading import Thread
from typing import Iterator
from typing import Mapping

from arms.ptftp._endpoints_registry import FileEndpointsRegistry
from arms.ptftp._server import TFTPServer

_max_datagram_size = (2 ** 16) - 1
_local_ip = '127.0.0.10'


class TestTFTPServer(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = Path(tempfile.mkdtemp())
        self._config_dir = self._tmp_dir / 'config'
        self._config_dir.mkdir()
        self._tftp_root_dir = self._tmp_dir / 'root'
        self._tftp_root_dir.mkdir()
        self._server_sock = _bind_local_udp_socket()
        self._server_address: tuple[str, int] = self._server_sock.getsockname()
        self._exception_queue = deque()
        self._thread = Thread(target=self._server_thread, daemon=True)
        self._thread.start()

    def _server_thread(self):
        listen_ip, listen_port = self._server_address
        endpoint_registry = FileEndpointsRegistry(self._config_dir)
        try:
            _logger.info("Start listening TFTP server on %s:%s", listen_ip, listen_port)
            tftp_server = TFTPServer(self._server_sock, endpoint_registry)
            try:
                tftp_server.serve_forever(16)
            except OSError as err:
                if err.errno != errno.EBADF:
                    _logger.info("Server socket is closed")
                    raise
        except Exception as err:
            _logger.exception("An exception happened")
            self._exception_queue.append(err)
            raise
        _logger.info("Server closed")

    def tearDown(self):
        self._server_sock.close()
        self._thread.join()
        try:
            raise self._exception_queue.pop()
        except IndexError:
            _logger.info("No exception were raised in the server thread")

    def test_get_file_by_absolute_path(self):
        expected_bytes = b'\x00' * (1024 * 5)
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        absolute_path = f'/{file.name}'
        received_bytes = _local_tftp_get(absolute_path, self._server_address)
        self.assertEqual(received_bytes, expected_bytes)

    def test_get_file_last_block_not_full(self):
        expected_bytes = b'\x00' * ((1024 * 5) - 100)
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        received_bytes = _local_tftp_get(file.name, self._server_address)
        self.assertEqual(received_bytes, expected_bytes)

    def test_get_file_last_block_empty(self):
        expected_bytes = b'\x00' * (1024 * 5)
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        received_bytes = _local_tftp_get(file.name, self._server_address)
        self.assertEqual(received_bytes, expected_bytes)

    def test_change_root(self):
        first_root_dir = self._tftp_root_dir / "first_root_dir"
        first_root_dir.mkdir()
        second_root_dir = self._tftp_root_dir / "second_root_dir"
        second_root_dir.mkdir()
        file_name = "irrelevant"
        first_file = first_root_dir / file_name
        second_file = second_root_dir / file_name
        first_expected_bytes = b'\x00' * (1024 * 5)
        second_expected_bytes = b'\xFF' * (1024 * 5)
        first_file.write_bytes(first_expected_bytes)
        second_file.write_bytes(second_expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(first_root_dir))
        first_received_bytes = _local_tftp_get(file_name, self._server_address)
        self.assertEqual(first_received_bytes, first_expected_bytes)
        config_file.write_text(str(second_root_dir))
        second_received_bytes = _local_tftp_get(file_name, self._server_address)
        self.assertEqual(second_received_bytes, second_expected_bytes)

    def test_request_block_size(self):
        arbitrary_file_size = 1024 * 3
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        arbitrary_block_size = 1468
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest(file.name, {'blksize': str(arbitrary_block_size)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_block_size = options_ack.options.get('blksize')
            self.assertEqual(int(negotiated_block_size), arbitrary_block_size)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            first_block_datagram, _address = _receive_local_datagram(client_sock)
        block = _Block.from_bytes(first_block_datagram)
        self.assertEqual(block.data, b'\x00' * arbitrary_block_size)

    def test_one_sec_request_timeout(self):
        arbitrary_file_size = 1024 * 3
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        one_sec_timeout = 1
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest(file.name, {'timeout': str(one_sec_timeout)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_timeout = options_ack.options.get('timeout')
            self.assertEqual(int(negotiated_timeout), one_sec_timeout)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            _first_block_datagram, _address = _receive_local_datagram(client_sock)
            start_at = time.monotonic()
            _first_block_repeat_datagram, _address = _receive_local_datagram(client_sock)
        repeat_interval = time.monotonic() - start_at
        _logger.info("Computed repeat interval: %s", repeat_interval)
        self.assertTrue(one_sec_timeout <= repeat_interval <= one_sec_timeout * 1.1)

    def test_three_sec_request_timeout(self):
        arbitrary_file_size = 1024 * 3
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        three_sec_timeout = 3
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest(file.name, {'timeout': str(three_sec_timeout)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_timeout = options_ack.options.get('timeout')
            self.assertEqual(int(negotiated_timeout), three_sec_timeout)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            _first_block_datagram, _address = _receive_local_datagram(client_sock)
            start_at = time.monotonic()
            _first_block_repeat_datagram, _address = _receive_local_datagram(client_sock)
        repeat_interval = time.monotonic() - start_at
        _logger.info("Computed repeat interval: %s", repeat_interval)
        self.assertTrue(three_sec_timeout <= repeat_interval <= three_sec_timeout * 1.1)

    def test_request_file_size(self):
        arbitrary_file_size = 1024 * 5
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest(file.name, {'tsize': '0'})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
        received_file_size = options_ack.options.get('tsize')
        self.assertEqual(int(received_file_size), arbitrary_file_size)

    def test_early_termination(self):
        # Sometimes, a Raspberry does an early termination.
        arbitrary_file_size = 1024 * 5
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        timeout = 1
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest(file.name, {'timeout': str(timeout)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_timeout = options_ack.options.get('timeout')
            self.assertEqual(int(negotiated_timeout), timeout)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            error = _Error(0x0, "Early Terminate")
            client_sock.sendto(error.as_bytes(), session_address)
            _first_block_datagram, _address = _receive_local_datagram(client_sock)
            client_sock.settimeout(timeout * 3)
            with self.assertRaises(TimeoutError):
                _receive_local_datagram(client_sock)

    def test_timeout_flow(self):
        arbitrary_file_size = 1024 * 5
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        timeout = 1
        with _bind_local_udp_socket() as client_sock:
            client_sock.settimeout(timeout * 3)
            read_request = _ReadRequest(file.name, {'timeout': str(timeout)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_timeout = options_ack.options.get('timeout')
            self.assertEqual(int(negotiated_timeout), timeout)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            _wait_first_block(client_sock, 5)
            timeout_error, _address = _receive_local_datagram(client_sock)
            error = _Error.from_bytes(timeout_error)
            self.assertEqual(error.code, 0x0)
            self.assertIn('unacknowledged', error.message)

    def test_ignore_non_tftp_traffic(self):
        arbitrary_file_size = 1024 * 5
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        flood_data = b'\xFF' * 10
        with _bind_local_udp_socket() as flood_socket:
            flood_socket.settimeout(1)
            flood_socket.sendto(flood_data, self._server_address)
            flood_socket.sendto(flood_data, self._server_address)
            flood_socket.sendto(flood_data, self._server_address)
            with self.assertRaises(TimeoutError):
                _receive_local_datagram(flood_socket)

    def test_ignore_non_session_traffic(self):
        arbitrary_file_size = 1024 * 5
        expected_bytes = b'\x00' * arbitrary_file_size
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        timeout = 1
        flood_data = b'\xFF' * 10
        with _bind_local_udp_socket() as client_sock, _bind_non_local_udp_socket() as flood_socket:
            client_sock.settimeout(timeout * 3)
            read_request = _ReadRequest(file.name, {'timeout': str(timeout)})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_timeout = options_ack.options.get('timeout')
            self.assertEqual(int(negotiated_timeout), timeout)
            flood_socket.sendto(flood_data, session_address)
            flood_socket.sendto(flood_data, session_address)
            flood_socket.sendto(flood_data, session_address)
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            first_block_datagram, address = _receive_local_datagram(client_sock)
        block = _Block.from_bytes(first_block_datagram)
        self.assertEqual(block.number, 1)

    def test_get_non_existed_file(self):
        file_not_found_code = 0x01
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._config_dir))
        with _bind_local_udp_socket() as client_sock:
            read_request = _ReadRequest("nonexisting_file", {})
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            error_datagram, remote = _receive_local_datagram(client_sock)
        self.assertNotEqual(remote, self._server_address)
        error = _Error.from_bytes(error_datagram)
        self.assertEqual(error.code, file_not_found_code)

    def test_ignore_repeated_request(self):
        arbitrary_file_size = 1024 * 10
        expected_bytes = _repeated_bytes(arbitrary_file_size)
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        timeout = 5
        with _bind_local_udp_socket() as client_sock:
            client_sock.settimeout(timeout * 3)
            non_empty_options = {'timeout': str(timeout)}
            read_request = _ReadRequest(file.name, non_empty_options)
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            first_options_ack_datagram, first_session_address = _receive_local_datagram(client_sock)
            _OptionsAck.from_bytes(first_options_ack_datagram)
            time.sleep(1)  # Pretend that we did not receive the response.
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            second_options_ack_datagram, second_session_address = _receive_local_datagram(client_sock)
            _OptionsAck.from_bytes(second_options_ack_datagram)
            self.assertEqual(first_session_address, second_session_address)
            client_sock.sendto(_Ack(0).as_bytes(), second_session_address)
            received = bytearray()
            for block_data in _iter_block(client_sock):
                received.extend(block_data)
        self.assertEqual(bytes(received), expected_bytes)

    def test_wrap_block_numbers(self):
        minimal_block_size = 512
        short_int_max_value = 2 ** 16 - 1
        arbitrary_file_size = short_int_max_value * minimal_block_size * 2
        expected_bytes = _repeated_bytes(arbitrary_file_size)
        file = self._tftp_root_dir / "irrelevant"
        file.write_bytes(expected_bytes)
        config_file = self._config_dir / _local_ip
        config_file.write_text(str(self._tftp_root_dir))
        timeout = 5
        with _bind_local_udp_socket() as client_sock:
            client_sock.settimeout(timeout * 3)
            non_empty_options = {'timeout': str(timeout), 'blksize': str(minimal_block_size)}
            read_request = _ReadRequest(file.name, non_empty_options)
            client_sock.sendto(read_request.as_bytes(), self._server_address)
            options_ack_datagram, session_address = _receive_local_datagram(client_sock)
            options_ack = _OptionsAck.from_bytes(options_ack_datagram)
            negotiated_size = options_ack.options.get('blksize')
            self.assertEqual(negotiated_size, str(minimal_block_size))
            client_sock.sendto(_Ack(0).as_bytes(), session_address)
            received = bytearray()
            for _index, block_data in enumerate(_iter_block(client_sock)):
                received.extend(block_data)
            else:
                self.assertGreater(_index, short_int_max_value)
        self.assertEqual(bytes(received), expected_bytes)


def _repeated_bytes(count: int) -> bytes:
    byte_iterator = cycle(range(255))
    return bytes(next(byte_iterator) for _ in range(count))


def _wait_first_block(client_sock: socket.socket, retransmission_attempts: int):
    for _ in range(retransmission_attempts):
        first_block_datagram, _address = _receive_local_datagram(client_sock)
        block = _Block.from_bytes(first_block_datagram)
        if block.number != 1:
            raise RuntimeError(f"Received {block.number} instead of 1")


def _local_tftp_get(filename: str, remote: tuple[str, int]) -> bytes:
    received = bytearray()
    with _bind_local_udp_socket() as udp_socket:
        udp_socket.sendto(_ReadRequest(filename, {}).as_bytes(), remote)
        for block_data in _iter_block(udp_socket):
            received.extend(block_data)
    return bytes(received)


def _bind_local_udp_socket() -> socket.socket:
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    sock.bind((_local_ip, 0))
    return sock


def _bind_non_local_udp_socket() -> socket.socket:
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    sock.bind(('127.0.0.100', 0))
    return sock


def _receive_local_datagram(sock: socket.socket) -> tuple[bytes, tuple[str, int]]:
    datagram, (remote_ip, remote_port) = sock.recvfrom(_max_datagram_size)
    if remote_ip != _local_ip:
        raise RuntimeError(f"Non-local data received from {remote_ip}:{remote_port}: {datagram!r}")
    return datagram, (remote_ip, remote_port)


class _Opcodes:
    read_request = b'\x00\x01'
    data_block = b'\x00\x03'
    acknowledge = b'\x00\x04'
    error = b'\x00\x05'
    options_ack = b'\x00\x06'


class _ReadRequest:

    _transfer_mode = b'octet'

    def __init__(self, filename: str, options: Mapping[str, str]):
        self.filename = filename
        self.options = options

    def as_bytes(self) -> bytes:
        encoded_filename = self.filename.encode('ascii')
        result = bytearray(_Opcodes.read_request)
        result.extend(encoded_filename + b'\x00' + self._transfer_mode + b'\x00')
        for option, value in self.options.items():
            result.extend(option.encode('ascii') + b'\x00' + value.encode('ascii') + b'\x00')
        return result

    def __repr__(self):
        return f'<ReadRequest: {self.filename}>'


class _Block:

    def __init__(self, number: int, data: bytes):
        self.number = number
        self.data = data

    @classmethod
    def from_bytes(cls, raw: bytes):
        opcode, message = _split_message(raw)
        if opcode != _Opcodes.data_block:
            raise RuntimeError(f"It is not a Block message. Opcode is {opcode}")
        block_number = int.from_bytes(message[:2], byteorder="big")
        return cls(block_number, message[2:])

    def __repr__(self):
        return f'<Block: len={len(self.data)}>'


class _Ack:

    def __init__(self, block_num: int):
        self.block_num = block_num

    def as_bytes(self) -> bytes:
        return _Opcodes.acknowledge + self.block_num.to_bytes(2, byteorder="big")

    def __repr__(self):
        return f'<ACK block: {self.block_num}>'


class _Error:

    def __init__(self, error_code: int, message: str):
        self.code = error_code
        self.message = message

    @classmethod
    def from_bytes(cls, raw: bytes):
        opcode, message = _split_message(raw)
        if opcode != _Opcodes.error:
            raise RuntimeError(f"It is not a Block message. Opcode is {opcode}")
        code = int.from_bytes(raw[2:4], byteorder="big")
        return cls(code, raw[4:-1].decode('ascii'))

    def as_bytes(self) -> bytes:
        error_code_encoded = self.code.to_bytes(2, byteorder="big")
        return _Opcodes.error + error_code_encoded + self.message.encode('ascii') + b'\x00'

    def __repr__(self):
        return f'<TFTP Error [{self.code}]: {self.message}>'


class _OptionsAck:

    def __init__(self, options: Mapping[str, str]):
        self.options = options

    @classmethod
    def from_bytes(cls, raw: bytes):
        opcode, options_string = _split_message(raw)
        if opcode != _Opcodes.options_ack:
            raise RuntimeError(f"It is not a Options Acknowledge message. Opcode is {opcode}")
        options = _parse_options(options_string)
        return cls(options)

    def __repr__(self):
        return f'<TFTP Options Acknowledge: {self.options}>'


def _parse_options(options_string: bytes) -> Mapping[str, str]:
    options_list = options_string.rstrip(b'\x00').split(b'\x00')
    options_iterator = iter(option.decode('ascii') for option in options_list)
    return dict(zip(options_iterator, options_iterator))


def _split_message(tftp_datagram: bytes) -> tuple[bytes, bytes]:
    return tftp_datagram[:2], tftp_datagram[2:]


def _iter_block(udp_socket: socket.socket) -> Iterator[bytes]:
    expected_block_number = 1
    expected_block_size = 0
    while True:
        block_datagram, remote = _receive_local_datagram(udp_socket)
        block = _Block.from_bytes(block_datagram)
        udp_socket.sendto(_Ack(block.number).as_bytes(), remote)
        if block.number == expected_block_number:
            expected_block_number = (expected_block_number + 1) % 65536
            yield block.data
            block_size = len(block.data)
            if block_size < expected_block_size:
                return
            expected_block_size = block_size


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s",
        )
    unittest.main()
