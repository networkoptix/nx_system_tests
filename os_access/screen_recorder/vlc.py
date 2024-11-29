# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import socket
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from pathlib import PurePath
from pathlib import PurePosixPath
from pathlib import PureWindowsPath
from subprocess import TimeoutExpired
from subprocess import list2cmdline
from typing import Collection
from typing import Optional
from typing import cast

from _internal.service_registry import default_prerequisite_store
from os_access import OsAccess
from os_access import PosixAccess
from os_access import WindowsAccess
from os_access import copy_file
from os_access.windows_graphic_app import start_in_graphic_mode

_logger = logging.getLogger(__name__)


class ScreenRecording(metaclass=ABCMeta):

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop_and_save(self, local_artifact_dir: Path):
        pass

    @contextmanager
    def record_video(self, local_artifact_dir: Path) -> AbstractContextManager[None]:
        self.start()
        try:
            yield
        finally:
            self.stop_and_save(local_artifact_dir)


class VLCScreenRecording(ScreenRecording, metaclass=ABCMeta):

    def __init__(self, os_access: OsAccess, vlc: PurePath, port: Optional[int] = None):
        self._os_access = os_access
        self._internal_port = 12312
        self._port = port or self._internal_port
        self._path = None
        self._sock = None
        self._vlc = vlc

    def start(self):
        # Sometimes VLC has started, but we can't connect to it. Give it another chance.
        try:
            self._start()
        except VLCStartFailed as e:
            _logger.warning(str(e))
            try:
                self._start()
            except VLCStartFailed:
                # Only logging errors, not raising. Screen recording is not critical for the test,
                # and its behavior should not impact the test.
                _logger.exception("Failed to start screen recording")

    def stop_and_save(self, local_artifact_dir: Path):
        self._stop()
        if self._path is None or not self._path.exists():
            _logger.warning("Screen recording is not found")
        else:
            copy_file(self._path, local_artifact_dir / self._path.name)

    def _start(self):
        try:
            self._launch()
        except _VLCLaunchFailed as e:
            raise VLCStartFailed(str(e))
        try:
            self._connect(timeout=30)
        except _VLCCannotConnect:
            self._terminate()
            raise VLCStartFailed("VLC: Cannot connect; it might've crashed")
        else:
            self._set_up()
        finally:
            self._disconnect()

    @abstractmethod
    def _launch(self):
        pass

    def _set_up(self):
        timestamp = datetime.now()
        name = f'recording_{timestamp:%Y%m%d_%H%M%S}.mp4'
        video_dir = self._os_access.home() / 'Videos'
        video_dir.mkdir(exist_ok=True)
        self._path = video_dir / name
        _logger.debug("VLC: Record screen: %s", self._path)
        output = b':'.join([
            b'transcode{vcodec=h264,vb=1024,acodec=none}',
            b'std{mux=mp4,access=file,dst=%s}' % str(self._path).encode('utf8'),
            ])
        media = b' :'.join([
            b'screen://',
            b'screen-fps=15',
            *self._os_specific_parameters(),
            b'sout=#' + output,
            ])
        try:
            self._send(b'enqueue ' + media + b'\n')
            self._send(b'play\n')
            self._recv()
        except (ConnectionError, TimeoutError):
            _logger.exception("VLC: connection broken")

    def _stop(self):
        try:
            self._connect(timeout=0)
        except _VLCCannotConnect:
            _logger.error("VLC: Cannot connect to stop")
            return None
        try:
            self._send(b'stop\n')
            self._recv()
            self._send(b'shutdown\n')
            self._recv()
            self._send(b'quit\n')
            self._recv()
        except (ConnectionAbortedError, ConnectionResetError, TimeoutError):
            _logger.exception("VLC: connection broken")
        finally:
            self._disconnect()
        self._wait_until_vlc_exits()
        self._close()

    def _terminate(self):
        self._os_access.kill_all_by_name(self._vlc.name)

    def _connect(self, *, timeout: float):
        # It needs to ensure that connection is stable, especially for Ubuntu
        started_at = time.monotonic()
        while True:
            self._sock = socket.socket()
            self._sock.settimeout(2)
            try:
                self._sock.connect((self._os_access.address, self._port))
            except (ConnectionError, TimeoutError):
                _logger.debug("VLC: Cannot connect")
            else:
                if self._check_connected():
                    _logger.debug("VLC: Connected")
                    break
            if time.monotonic() - started_at > timeout:
                raise _VLCCannotConnect(f"Failed to connect to VLC in {timeout:.1f} seconds")
            self._sock.close()
            time.sleep(1)

    def _disconnect(self):
        self._sock.close()
        self._sock = None

    def _send(self, request: bytes):
        _logger.debug("VLC: Send: %s", request)
        self._sock.send(request)

    def _check_connected(self) -> bool:
        try:
            self._sock.send(b'help\n')
            data = self._sock.recv(4096)
        except (ConnectionError, TimeoutError):
            _logger.debug("VLC: Connection attempt failed")
            return False
        else:
            return not data == b''

    def _recv(self):
        while True:
            try:
                data = self._sock.recv(4096)
            except TimeoutError:
                _logger.debug("VLC: Would block")
                break
            _logger.debug("VLC: Recv: %s", data)
            if not data:
                _logger.debug("VLC: Peer disconnected")
                break

    def _wait_until_vlc_exits(self):
        timeout_sec = 20
        started_at = time.monotonic()
        while True:
            try:
                self._os_access.get_pid_by_name('vlc')
            except FileNotFoundError:
                break
            except TimeoutExpired:
                _logger.debug('Failed to get VLC status')
            else:
                _logger.debug('VLC is still working')
            if time.monotonic() - started_at > timeout_sec:
                _logger.error(
                    'VLC has working after %d seconds. The video file could be corrupted.',
                    timeout_sec)
                break
            time.sleep(1)

    @abstractmethod
    def _close(self):
        pass

    @abstractmethod
    def _os_specific_parameters(self) -> Collection[bytes]:
        pass


class VLCScreenRecordingWindows(VLCScreenRecording):

    def __init__(self, os_access, port: Optional[int] = None):
        super().__init__(os_access, PureWindowsPath(r'C:\Program Files\VideoLAN\VLC\vlc.exe'), port)

    def _launch(self):
        command = [
            self._vlc,
            '--intf', 'rc',
            '--rc-host', '0.0.0.0:' + str(self._internal_port),
            '--rc-quiet',
            '--no-crashdump',
            ]
        _logger.debug("VLC: Launch: %s", list2cmdline(command))
        windows_access = cast(WindowsAccess, self._os_access)
        start_in_graphic_mode(windows_access, command)
        started_at = time.monotonic()
        timeout_sec = 10
        while True:
            try:
                windows_access.get_pid_by_name('vlc')
            except FileNotFoundError:
                _logger.debug("VLC has not started yet")
            else:
                break
            if time.monotonic() - started_at > timeout_sec:
                raise _VLCLaunchFailed("VLC is not running after %.1f seconds", timeout_sec)
            time.sleep(0.5)

    def _close(self):
        # There is no need to do anything
        pass

    def _os_specific_parameters(self) -> Collection[bytes]:
        mouse_pointer = default_prerequisite_store.fetch('gui-testdata/mouse_pointer.png')
        # The VLC player is only able to find the file in the current directory.
        # The current directory for a scheduled task is C:\windows\system32
        copy_file(mouse_pointer, self._os_access.home() / 'mouse_pointer.png')
        # The screen-mouse-image parameter is supported only on Windows.
        # See to the VLC source code:
        #   vlc\modules\access\screen\screen.h
        #   vlc\modules\access\screen\screen.c
        return [b'screen-mouse-image=mouse_pointer.png']


class VLCScreenRecordingLinux(VLCScreenRecording):

    def __init__(self, os_access: OsAccess, display: int, authority_file: str, port: Optional[int] = None):
        super().__init__(os_access, PurePosixPath('vlc'), port)
        self._display = display
        self._authority_file = authority_file
        self._vlc_ssh_run = None

    def _launch(self):
        command = f'{str(self._vlc)} --intf rc --rc-host 0.0.0.0:{self._internal_port}'
        env = {
            'DISPLAY': f':{self._display}',
            'XAUTHORITY': str(self._authority_file),
            }
        _logger.debug("VLC: Launch: %s", command)
        posix_access = cast(PosixAccess, self._os_access)
        if self._vlc_ssh_run is not None:
            # It's important. This code may be called twice (see methods
            # _start() and start()), and in the second run, it must close
            # the previous channel.
            self._vlc_ssh_run.close()
        self._vlc_ssh_run = posix_access.shell.Popen(command, terminal=True, env=env)
        started_at = time.monotonic()
        timeout_sec = 10
        while True:
            try:
                posix_access.get_pid_by_name('vlc')
            except FileNotFoundError:
                _logger.debug("VLC has not started yet")
            else:
                break
            if time.monotonic() - started_at > timeout_sec:
                raise _VLCLaunchFailed("VLC is not running after %.1f seconds", timeout_sec)
            time.sleep(0.5)

    def _close(self):
        if self._vlc_ssh_run is not None:
            self._vlc_ssh_run.close()
            self._vlc_ssh_run = None

    def _os_specific_parameters(self) -> Collection[bytes]:
        return []


class VLCStartFailed(Exception):
    pass


class _VLCCannotConnect(Exception):
    pass


class _VLCLaunchFailed(Exception):
    pass
