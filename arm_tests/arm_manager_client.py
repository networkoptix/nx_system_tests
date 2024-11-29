# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import json
import logging
import socket
import subprocess
import time
from typing import Any
from typing import Iterable
from typing import Mapping
from typing import TypedDict
from typing import Union

from arm_tests.arm_networking import ArmNetworking
from arm_tests.machines_market import MachinesMarket
from arm_tests.machines_market import RunningMachine
from os_access import PosixAccess
from os_access import SftpPath
from os_access import Ssh
from os_access import SshNotConnected
from os_access._ssh_traffic_capture import SSHTrafficCapture

_logger = logging.getLogger(__name__)


class NOKError(Exception):
    pass


class ServerException(Exception):
    pass


class MachineTimeout(Exception):
    pass


class ServerStatus:
    OK = 'OK'
    NOK = 'NOK'
    ACK = 'ACK'
    SRV_GREET = 'GREET'
    SRV_ERR = 'ERROR'
    TIMEOUT = 'TIMEOUT'


class RequestType:

    UNLOCK_MACHINE = 'unlock_machine'
    GET_SNAPSHOT = 'get_snapshot'
    COMMIT_SNAPSHOT = 'commit_snapshot'


class LockedMachineClientInfo(TypedDict):
    machine_name: str
    ip_address: str
    ssh_port: int
    username: str
    ssh_key: str


class _RequestPriority:
    HIGH = 0
    MIDDLE = 1
    LOW = 2


class _ClientSession:
    _host = 'beg-ft002'
    _port = 1491

    def __init__(self):
        self._sock = self._open_socket()
        self._stream = self._sock.makefile('rwb')
        self._wait_greet()
        _logger.info("Successfully connected to %s:%s", self._host, self._port)

    def _open_socket(self) -> socket.socket:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
        server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1)
        server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 1)
        server_sock.connect((self._host, self._port))
        return server_sock

    def _wait_greet(self):
        [status, _, _] = self._read_response(timeout=5)
        if status != ServerStatus.SRV_GREET:
            raise RuntimeError(f"Expected {ServerStatus.SRV_GREET} message, got: {status}")
        _logger.info("Session is established")

    def _read_response(self, timeout: float) -> tuple[str, str, Mapping[str, Union[Iterable, int, str]]]:
        self._sock.settimeout(timeout)
        if not (line := self._stream.readline().strip()):
            raise RuntimeError("Server disconnected")
        self._sock.settimeout(None)
        (status, message, data) = json.loads(line.decode('utf-8'))
        _logger.info(
            "Received response with status: %s; message: %s; data: %s", status, message, data)
        return status, message, data

    def is_alive(self) -> bool:
        try:
            self._sock.getpeername()
        except OSError as err:
            if err.errno == errno.ENOTCONN:
                return False
            raise
        return True

    def read_status(self, timeout: float) -> Mapping[str, Union[Iterable, int, str]]:
        end = time.monotonic() + timeout
        next_message_timeout = timeout
        while True:
            [status, message, data] = self._read_response(timeout=next_message_timeout)
            if status == ServerStatus.SRV_ERR:
                raise ServerException(message)
            elif status == ServerStatus.NOK:
                raise NOKError(message)
            elif status == ServerStatus.TIMEOUT:
                raise MachineTimeout(message)
            elif status == ServerStatus.ACK:
                _logger.info("Acknowledge received : %s", message)
                next_message_timeout = end - time.monotonic()
                if next_message_timeout <= 0:
                    raise TimeoutError(f"Method timeout {timeout} expired")
                continue
            return data

    def send(self, request: str, request_data):
        to_send = [request, request_data]
        to_send = json.dumps(to_send)
        to_send = to_send.encode('utf-8')
        to_send = to_send + b'\r\n'
        self._stream.write(to_send)
        self._stream.flush()

    def close(self):
        _logger.info("Close connection")
        try:
            self._stream.close()
        except OSError as e:
            logging.error('', exc_info=e)
        self._sock.close()
        _logger.info("Client closed")


class ArmTrafficCapture(SSHTrafficCapture):

    def _start_capturing_command(self, capture_path, size_limit_bytes, duration_limit_sec):
        return self._shell.Popen(
            [
                'tshark',
                '-b', 'filesize:{:d}'.format(size_limit_bytes // 1024),
                '-a', 'duration:{:d}'.format(duration_limit_sec),
                '-w', capture_path,
                '-n',  # Disable network object name resolution
                '-i', 'any',  # Capture on all interfaces
                'not', 'port', '3260',  # Ignore ISCSI traffic
                ],
            terminal=True,
            )


class _ArmManagerMarket(MachinesMarket):

    def __init__(self, priority: int):
        self._priority = priority

    def lease(self, description: Mapping[str, Any]) -> '_ArmManagerMachine':
        request_timeout = 60
        request = {
            'description': description,
            'timeout': request_timeout,
            'priority': self._priority,
            }
        session = _ClientSession()
        session.send(RequestType.GET_SNAPSHOT, request)
        _logger.info("%r: Request: %s", self, request)
        data = session.read_status(timeout=request_timeout)
        [machine_data] = data['clients']  # type: LockedMachineClientInfo
        return _ArmManagerMachine(session, machine_data)

    def __repr__(self):
        return f'{self.__class__.__name__}()'


class HighPriorityMarket(_ArmManagerMarket):

    def __init__(self):
        super().__init__(_RequestPriority.HIGH)


class MiddlePriorityMarket(_ArmManagerMarket):

    def __init__(self):
        super().__init__(_RequestPriority.MIDDLE)


class LowPriorityMarket(_ArmManagerMarket):

    def __init__(self):
        super().__init__(_RequestPriority.LOW)


def _clock_synchronised(os_access: PosixAccess) -> bool:
    if not os_access.service('systemd-timesyncd.service').is_running():
        return False
    try:
        result = os_access.shell.run(['timedatectl', 'status'])
    except subprocess.CalledProcessError:
        return False
    output = result.stdout.decode('utf-8')
    for line in output.splitlines():
        if 'System clock synchronized' in line:
            [_, is_synchronised] = line.split(':')
            return is_synchronised.strip() == 'yes'
    else:
        return False


def _wait_for_machine_online(os_access: PosixAccess, machine_wait_timeout: float) -> float:
    started_at = time.monotonic()
    sleep_delay = 1
    finish_at = started_at + machine_wait_timeout
    while True:
        try:
            if os_access.is_ready():
                _logger.info("Successfully connected to %r", os_access)
                remaining = finish_at - time.monotonic()
                return remaining
        except ConnectionResetError:
            pass
        except SshNotConnected:
            pass
        if time.monotonic() > finish_at:
            raise TimeoutError("Logs parsing timed out")
        time.sleep(sleep_delay)


def _wait_for_clock_synchronised(os_access: PosixAccess, machine_wait_timeout: float):
    finish_at = time.monotonic() + machine_wait_timeout
    sleep_delay = 1
    while time.monotonic() < finish_at:
        remaining = finish_at - time.monotonic()
        if _clock_synchronised(os_access):
            return
        if remaining < sleep_delay:
            time.sleep(remaining)
        else:
            time.sleep(sleep_delay)
    raise TimeoutError("The clock did not synchronise")


def _wait_for_machine_ready(os_access: PosixAccess):
    # Currently, execution time is greatly increased due to usage of a FastEthernet switch which
    # heavily impacts write performance decreasing it from 30 to 5 MBps.
    machine_wait_timeout = 180
    remaining_timeout = _wait_for_machine_online(os_access, machine_wait_timeout)
    _wait_for_clock_synchronised(os_access, remaining_timeout)


class _ArmManagerMachine(RunningMachine):

    def __init__(self, session: _ClientSession, machine_data: LockedMachineClientInfo):
        self._session = session
        self._machine_data = machine_data

    def monitor(self, timeout: float):
        end_at = time.monotonic() + timeout
        while True:
            if not self._session.is_alive():
                raise RuntimeError(f"{self} has gone")
            if time.monotonic() > end_at:
                return
            time.sleep(0.5)

    def get_os_access(self) -> PosixAccess:
        ssh = Ssh(
            self._machine_data['ip_address'],
            self._machine_data['ssh_port'],
            self._machine_data['username'],
            self._machine_data['ssh_key'],
            )
        capture_dir = SftpPath(ssh, '/var/nx-traffic-capture')
        traffic_capture = ArmTrafficCapture(ssh, capture_dir)
        os_access = PosixAccess(
            address=self._machine_data['ip_address'], port_map=None,
            shell=ssh,
            traffic_capture=traffic_capture,
            networking=ArmNetworking(ssh),
            )
        _wait_for_machine_ready(os_access)
        return os_access

    def commit(self):
        self._session.send(
            RequestType.COMMIT_SNAPSHOT, {'machine_name': self._machine_data['machine_name']})
        # TODO: Find out why it may take more than 30 seconds.
        self._session.read_status(timeout=60)

    def unlock(self):
        self._session.send(
            RequestType.UNLOCK_MACHINE, {'machine_name': self._machine_data['machine_name']})
        self._session.read_status(timeout=5)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()

    def __repr__(self):
        return f"<RunningMachine {self._machine_data['machine_name']}>"
