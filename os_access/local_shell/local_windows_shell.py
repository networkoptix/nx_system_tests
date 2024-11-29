# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import _winapi
import asyncio.windows_utils  # noqa: I100,I201  # _winapi is not 3rd-party.
import logging
import subprocess

from os_access._command import Run
from os_access._command import Shell

_logger = logging.getLogger(__name__)


class _Stream:

    def __init__(self, name, handle):
        self._name = name
        self._handle = handle
        self.closed = False
        self._start_read()

    def _start_read(self):
        _logger.debug("%s: ReadFile: start", self._name)
        assert not self.closed
        try:
            result, err = _winapi.ReadFile(self._handle, 10000, overlapped=True)
        except BrokenPipeError as e:
            _logger.debug("%s: ReadFile: closed: %r", self._name, e)
            del self._ov, self.event
            self.closed = True
            return
        _logger.debug("%s: ReadFile: result %d (%r)", self._name, err, result)
        assert err in (0, _winapi.ERROR_IO_PENDING)
        self._ov = result
        self.event = self._ov.event

    def read(self):
        if self.closed:
            return None
        try:
            n_read, err = self._ov.GetOverlappedResult(
                False,  # Whether to wait for result. If ready, returns immediately.
                )
        except BrokenPipeError as e:
            _logger.debug(
                "%s: GetOverlappedResult: closed %s: %r",
                self._name, 'before' if self.closed else 'just now', e)
            self.closed = True
            del self._ov, self.event
            return None
        if err == 0:
            buffer = self._ov.getbuffer()
            _logger.debug(
                "%s: GetOverlappedResult: success: %d bytes",
                self._name, len(buffer))
            assert len(buffer) == n_read
            self._start_read()
            return buffer
        if err == 996:
            _logger.debug(
                "%s: GetOverlappedResult: error %d (%s)",
                self._name, err, 'ERROR_IO_INCOMPLETE')
            return b''
        raise OSError(err)

    def __del__(self):
        self.close()

    def close(self):
        if hasattr(self, '_ov'):
            self._ov.cancel()  # OK to cancel Overlapped that is not in progress
            del self._ov
        if hasattr(self, '_handle'):  # A handle can be closed only once
            _winapi.CloseHandle(self._handle)
            del self._handle


def _duplicated_handle(stream):
    current_process = _winapi.GetCurrentProcess()
    return _winapi.DuplicateHandle(
        current_process, stream.fileno(), current_process,
        0, False, _winapi.DUPLICATE_SAME_ACCESS)


class _LocalWindowsRun(Run):

    def __init__(self, subprocess_run: subprocess.Popen):
        super(_LocalWindowsRun, self).__init__(subprocess_run.args)
        self._subprocess_run = subprocess_run
        self._stdout = _Stream('StdOut', _duplicated_handle(subprocess_run.stdout))
        self._stderr = _Stream('StdErr', _duplicated_handle(subprocess_run.stderr))

    def receive(self, timeout_sec):
        events = [self._subprocess_run._handle]
        if not self._stdout.closed:
            events.append(self._stdout.event)
        if not self._stderr.closed:
            events.append(self._stderr.event)
        _winapi.WaitForMultipleObjects(
            events,
            False,  # False - wait for first, True - wait for all.
            int(timeout_sec * 1000),
            )
        # If both streams are ready, return both chunks of data.
        return self._stdout.read(), self._stderr.read()

    def send(self, bytes_buffer: bytes, is_last=False) -> int:
        size_written, error = _winapi.WriteFile(
            self._subprocess_run.stdin.fileno(),
            bytes_buffer,
            overlapped=False,  # Writes are synchronous.
            )
        assert error == 0
        assert size_written == len(bytes_buffer)
        if is_last:
            _winapi.CloseHandle(self._subprocess_run.stdin.fileno())
        return size_written

    @property
    def returncode(self):
        # On Windows, if Popen.poll() is not called,
        # Popen.returncode is not set.
        return self._subprocess_run.poll()

    @property
    def pid(self):
        return self._subprocess_run.pid

    def wait(self, timeout=None):
        return self._subprocess_run.wait(timeout=timeout)

    def terminate(self):
        return self._subprocess_run.terminate()

    def kill(self):
        return self._subprocess_run.kill()

    def close(self):
        self._stdout.close()
        self._stderr.close()


class _LocalWindowsShell(Shell):

    def Popen(self, args, shell=False, **kwargs):
        # asyncio.windows_utils.Popen creates subprocess.Popen object with
        # Windows pipes, which are exactly what is needed in this case.
        # TODO: Create pipes here, don't use Popen from asyncio or subprocess.
        process = asyncio.windows_utils.Popen(
            args,
            stdin=asyncio.windows_utils.PIPE,
            stdout=asyncio.windows_utils.PIPE,
            stderr=asyncio.windows_utils.PIPE,
            shell=shell,
            )
        return _LocalWindowsRun(process)

    def is_working(self):
        return True


local_windows_shell = _LocalWindowsShell()
