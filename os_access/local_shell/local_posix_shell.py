# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import logging
import os
import signal
import subprocess
import time
from collections import namedtuple
from selectors import DefaultSelector
from selectors import EVENT_READ

from os_access._command import Run
from os_access._posix_shell import PosixShell
from os_access._posix_shell import augment_script
from os_access._posix_shell import command_to_script
from os_access._posix_shell import env_values_to_str

_logger = logging.getLogger(__name__)


class _LocalPosixRun(Run):
    _Stream = namedtuple('_Stream', ['name', 'file_obj'])

    def __init__(self, *popenargs, **popenkwargs):
        process = subprocess.Popen(*popenargs, **popenkwargs)
        super().__init__(process.args)
        self._process = process
        self._poller = DefaultSelector()
        self._streams = {}  # Indexed by their fd.
        if self._process.stdout:
            self._register_and_append('stdout', self._process.stdout)
        if self._process.stderr:
            self._register_and_append('stderr', self._process.stderr)

    def _register_and_append(self, name, file_obj):
        fd = file_obj.fileno()
        self._streams[fd] = self._Stream(name, file_obj)
        _logger.debug("%s: Register file descriptor %d", name, fd)
        self._poller.register(fd, EVENT_READ)

    def _close_unregister_and_remove(self, fd):
        name = self._streams[fd].name
        _logger.debug("%s: Unregister file descriptor %d", name, fd)
        self._poller.unregister(fd)
        self._streams[fd].file_obj.close()
        del self._streams[fd]

    def send(self, bytes_buffer, is_last=False):
        # Blocking call, no need to use polling functionality.
        try:
            bytes_written = self._process.stdin.write(bytes_buffer)
            if is_last and bytes_written == len(bytes_buffer):
                self._process.stdin.close()
            return bytes_written
        except OSError as e:
            if e.errno != errno.EPIPE:
                raise
            # Ignore EPIPE: -- behave as if everything has been written.
            _logger.getChild('stdin').debug("EPIPE.")
            self._process.stdin.close()
            return len(bytes_buffer)

    @property
    def returncode(self):
        return self._process.poll()

    @property
    def pid(self):
        return self._process.pid

    def _poll_exit_status(self, timeout_sec):
        # TODO: Use combination of alert() and os.waitpid(): https://stackoverflow.com/a/282190/1833960.
        if self._process.poll() is None:
            _logger.debug("Hasn't exited. Sleep for %.3f seconds.", timeout_sec)
            time.sleep(timeout_sec)
        else:
            _logger.info("Process exited, not streams open -- this must be last call.")
        return self._process.poll()

    def _poll_streams(self, timeout_sec):
        return [selector_key.fileobj for selector_key, _ in self._poller.select(timeout_sec)]

    def receive(self, timeout_sec):
        name2data = {}
        if self._streams:
            for fd in self._poll_streams(timeout_sec):
                stream = self._streams[fd]
                chunk = os.read(fd, 16 * 1024)
                if not chunk:
                    self._close_unregister_and_remove(fd)
                name2data[stream.name] = chunk

        for stream in self._streams.values():
            name2data.setdefault(stream.name, b'')
        return name2data.get('stdout'), name2data.get('stderr')

    def close(self):
        for fd in list(self._streams):  # List is preserved during iteration. Dict is emptying.
            self._close_unregister_and_remove(fd)
        self._poller.close()

    def terminate(self):
        self._process.send_signal(signal.SIGTERM)

    def kill(self):
        self._process.send_signal(signal.SIGKILL)

    def wait(self, timeout=None):
        return self._process.wait(timeout=timeout)


class _LocalPosixShell(PosixShell):

    def __repr__(self):
        return '<LocalShell>'

    @staticmethod
    def _make_kwargs(cwd, env):
        kwargs = {
            'close_fds': True,
            'bufsize': 0,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'stdin': subprocess.PIPE}
        if cwd is not None:
            kwargs['cwd'] = str(cwd)
        if env is not None:
            kwargs['env'] = {name: str(value) for name, value in env.items()}
        return kwargs

    def is_working(self):
        return True

    @classmethod
    def Popen(cls, command, cwd=None, env=None):
        if isinstance(command, str):
            set_eux = '\n' in command
            script_to_run = augment_script(command, set_eux=set_eux)
            script_to_log = augment_script(command, cwd=cwd, env=env, set_eux=set_eux)
            _logger.info('Run local script:\n%s', script_to_log)
            kwargs = cls._make_kwargs(cwd, env_values_to_str(env) if env else None)
            return _LocalPosixRun(script_to_run, shell=True, **kwargs)
        kwargs = cls._make_kwargs(cwd, env)
        command = [str(arg) for arg in command]
        _logger.info('Run: %s', command_to_script(command))
        return _LocalPosixRun(command, shell=False, **kwargs)

    def close(self):
        """Explicitly do nothing to close local shell."""
        pass


local_posix_shell = _LocalPosixShell()
