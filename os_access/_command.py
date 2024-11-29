# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from subprocess import CalledProcessError
from subprocess import CompletedProcess
from subprocess import SubprocessError
from subprocess import TimeoutExpired
from typing import Optional
from typing import Union

_logger = logging.getLogger(__name__)

_DEFAULT_RUN_TIMEOUT_SEC = 60

# In Python "bytes" in a type annotation denotes any of the following.
# But PyCharm doesn't respect memoryview.
_Bytes = Union[bytes, bytearray, memoryview]


class _CalledProcessError(CalledProcessError):

    def __str__(self):
        stderr = self.stderr.decode(errors='backslashreplace')[:5000]
        if self.returncode is None:
            result = "no exit status"
        else:
            result = f"exit status {self.returncode} (0x{self.returncode:x})"
        return f"Command {self.cmd} died with {result}: {stderr}"


class _Buffer:
    _line_beginning_skipped = "(Line beginning was skipped.) "

    def __init__(self, name):
        self._name = name
        self._chunks = []
        self.closed = False

    def write(self, chunk: Optional[_Bytes]):
        if chunk is None:
            if not self.closed:
                self.closed = True
                _logger.debug("%s: closed", self._name)
        else:
            assert not self.closed
            if chunk:
                self._chunks.append(chunk)
                chunk_decoded = chunk.decode(errors='backslashreplace')
                _logger.debug("%s: data: %s", self._name, chunk_decoded)

    def read(self):
        data = b''.join(self._chunks)
        self._chunks = []
        return data


class Run(metaclass=ABCMeta):

    _defensive_timeout = 30

    def __init__(self, args):
        self.args = args

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.returncode is not None:
            self.close()
            return
        try:
            self.kill()
        except NotImplementedError:
            kill = "kill not implemented"
        else:
            kill = "kill attempted"
        try:
            self.wait(self._defensive_timeout)
        except TimeoutExpired:
            waiting = "timed out"
        else:
            waiting = "successfully stopped"
        self.close()
        message = f"Command '%s' was working when __exit__ called, {kill}, {waiting}"
        if exc_type is None:
            raise SubprocessError(message % self.args)
        _logger.warning(message, self.args)

    @abstractmethod
    def wait(self, timeout=None) -> int:
        pass

    @abstractmethod
    def send(self, bytes_buffer: _Bytes, is_last=False) -> int:
        return 0

    @abstractmethod
    def receive(self, timeout_sec: float):
        """Receive stdout chunk and stderr chunk; None if closed."""
        return b'', b''

    @property
    @abstractmethod
    def returncode(self) -> Optional[int]:
        return None

    def communicate(
            self,
            input: Optional[_Bytes] = None,  # noqa PyShadowingBuiltins
            timeout_sec: float = _DEFAULT_RUN_TIMEOUT_SEC,
            ) -> (bytes, bytes):
        # If input bytes not None but empty, send zero bytes once.
        left_to_send = None if input is None else memoryview(input)
        stdout = _Buffer('stdout')
        stderr = _Buffer('stderr')
        started_at = time.monotonic()
        while True:
            _logger.debug("Receive data")
            # The self.returncode variable must be cached first due to the fact that
            # Paramiko processes data and sets returncode in another thread. So, a race condition
            # is possible between calls to self.receive() and self.returncode.
            # To ensure all data is received, save a return code into the local variable
            # to be checked strictly after calling self.receive().
            returncode = self.returncode
            chunks = self.receive(timeout_sec=min(1., timeout_sec / 2.))
            for buffer, chunk in zip((stdout, stderr), chunks):
                buffer.write(chunk)
            _logger.debug(
                "Exit status: %s; stdout: %s, stderr: %s",
                self.returncode,
                'closed' if stdout.closed else 'open',
                'closed' if stderr.closed else 'open',
                )
            if returncode is not None and stdout.closed and stderr.closed:
                _logger.debug("Exit clean.")
                break
            if time.monotonic() - started_at > timeout_sec:
                if returncode is not None:
                    _logger.debug("Exit with streams not closed.")
                    break
                stdout = stdout.read()
                stderr = stderr.read()
                raise TimeoutExpired(self.args, timeout_sec, stdout, stderr)
            if left_to_send is None:
                continue
            if returncode is not None:
                _logger.error("Exit with data yet to send.")
                continue
            sent_bytes = self.send(left_to_send, is_last=True)
            left_to_send = left_to_send[sent_bytes:]
            if not left_to_send:
                left_to_send = None

        return stdout.read(), stderr.read()

    @abstractmethod
    def terminate(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @abstractmethod
    def close(self):
        pass


class Shell(metaclass=ABCMeta):

    @abstractmethod
    def Popen(self, args, **kwargs) -> Run:  # noqa PyPep8Naming
        pass

    def run(
            self,
            args,
            input: Optional[_Bytes] = None,  # noqa PyShadowingBuiltins
            timeout_sec: float = _DEFAULT_RUN_TIMEOUT_SEC,
            check=True,
            **kwargs) -> CompletedProcess:
        with self.Popen(args, **kwargs) as run:
            stdout, stderr = run.communicate(input=input, timeout_sec=timeout_sec)
            if check and run.returncode != 0:
                raise _CalledProcessError(run.returncode, args, stdout, stderr)
            return CompletedProcess(args, run.returncode, stdout, stderr)
