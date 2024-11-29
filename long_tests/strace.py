# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from contextlib import contextmanager

from os_access import PosixAccess
from os_access import RemotePath


@contextmanager
def strace(os_access: PosixAccess, pid: int) -> RemotePath:
    s = _Strace(os_access)
    s.start(pid)
    try:
        yield s.get_log_path()
    finally:
        s.stop()


class _Strace:

    def __init__(self, os_access: PosixAccess):
        if not isinstance(os_access, PosixAccess):
            raise NotImplementedError("Only Linux supported")
        self._os_access = os_access
        self._strace_ssh_run = None
        self._current_log_path = None

    def start(self, pid: int):
        log_path = f'/var/log/strace_{pid}.log'
        command = f'strace -f -e trace=/.?write.?,/.?read.? -qq -y -p {pid} -o {log_path}'
        _logger.debug("strace running: %s", command)
        if self._strace_ssh_run is not None:
            raise _StraceAlreadyStarted("strace already started")
        self._strace_ssh_run = self._os_access.shell.Popen(command, terminal=True)
        self._current_log_path = self._os_access.path(log_path)
        started_at = time.monotonic()
        while True:
            try:
                self._os_access.get_pid_by_name('strace')
            except FileNotFoundError:
                _logger.debug("strace has not started yet")
            else:
                break
            if time.monotonic() - started_at > 3:
                stdout, stderr = self._strace_ssh_run.receive(timeout_sec=3)
                self._strace_ssh_run.close()
                self._strace_ssh_run = None
                raise _StraceStartFailed(
                    f"strace failed to start.\n"
                    f"Stdout:\n{stdout}\n"
                    f"Stderr:\n{stderr}")
            time.sleep(0.5)

    def stop(self):
        if self._strace_ssh_run is None:
            raise _StraceNotStarted()
        self._strace_ssh_run.terminate()
        started_at = time.monotonic()
        while True:
            try:
                self._os_access.get_pid_by_name('strace')
            except FileNotFoundError:
                break
            else:
                _logger.debug("strace has not stopped yet")
            if time.monotonic() - started_at > 10:
                stdout, stderr = self._strace_ssh_run.receive(timeout_sec=3)
                self._strace_ssh_run.close()
                self._strace_ssh_run = None
                raise _StraceStopFailed(
                    f"strace failed to stop.\n"
                    f"Stdout:\n{stdout}\n"
                    f"Stderr:\n{stderr}")
            time.sleep(0.5)
        stdout, stderr = self._strace_ssh_run.receive(timeout_sec=3)
        _logger.debug("strace stopped.\nStdout:\n%s\nStderr:\n%s", stdout, stderr)
        self._strace_ssh_run.close()
        self._strace_ssh_run = None

    def get_log_path(self) -> RemotePath:
        return self._current_log_path


class _StraceAlreadyStarted(Exception):
    pass


class _StraceNotStarted(Exception):
    pass


class _StraceStartFailed(Exception):
    pass


class _StraceStopFailed(Exception):
    pass


_logger = logging.getLogger(__name__)
