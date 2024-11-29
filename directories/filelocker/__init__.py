# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import platform
import random
import time
from contextlib import contextmanager
from pathlib import Path

__all__ = [
    'AlreadyLocked',
    'FileLockDirectory',
    'downgrade_lock',
    'try_lock_exclusively',
    'try_lock_shared',
    'try_locked',
    'wait_locked_exclusively',
    'wait_until_locked',
    ]


class AlreadyLocked(Exception):
    pass


_platform = platform.system()


if _platform == "Windows":
    from ctypes import GetLastError
    from ctypes import POINTER
    from ctypes import Structure
    from ctypes import windll
    from ctypes.wintypes import BOOL
    from ctypes.wintypes import DWORD
    from ctypes.wintypes import HANDLE
    from ctypes.wintypes import LPVOID
    from ctypes.wintypes import ULONG
    from msvcrt import get_osfhandle

    # See: https://docs.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-overlapped
    class Overlapped(Structure):
        _fields_ = [
            ('Internal', POINTER(ULONG)),
            ('InternalHigh', POINTER(ULONG)),
            ('hEvent', HANDLE),
            ('Pointer', LPVOID),
            ]

    windll.kernel32.LockFileEx.argtypes = HANDLE, DWORD, DWORD, DWORD, DWORD, Overlapped
    windll.kernel32.LockFileEx.restype = BOOL

    _stub_overlapped = Overlapped()
    LOCKFILE_EXCLUSIVE_LOCK = 0x2
    LOCKFILE_FAIL_IMMEDIATELY = 0x1

    def try_lock_exclusively(fileno: int) -> bool:
        handle = get_osfhandle(fileno)
        # See: https://docs.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex
        flags = LOCKFILE_FAIL_IMMEDIATELY | LOCKFILE_EXCLUSIVE_LOCK
        return windll.kernel32.LockFileEx(handle, flags, 0, 1, 0, _stub_overlapped)

    def try_lock_shared(fileno: int) -> bool:
        handle = get_osfhandle(fileno)
        # See: https://docs.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex
        flags = LOCKFILE_FAIL_IMMEDIATELY
        return windll.kernel32.LockFileEx(handle, flags, 0, 1, 0, _stub_overlapped)

    def downgrade_lock(fileno: int):
        """Transform exclusive lock to shared.

        See: https://docs.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex
        A shared lock can overlap an exclusive lock if both locks were
        created using the same file handle. When a shared lock overlaps
        an exclusive lock, the only possible access is a read by the owner
        of the locks. If the same range is locked with an exclusive and
        a shared lock, two unlock operations are necessary to unlock the
        region; the first unlock operation unlocks the exclusive lock,
        the second unlock operation unlocks the shared lock.
        """
        handle = get_osfhandle(fileno)
        flags = LOCKFILE_FAIL_IMMEDIATELY
        assert windll.kernel32.LockFileEx(handle, flags, 0, 1, 0, _stub_overlapped)
        assert windll.kernel32.UnlockFileEx(handle, 0, 1, 0, _stub_overlapped)

    def _wait_until_locked(fileno: int):
        handle = get_osfhandle(fileno)
        # See: https://docs.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex
        flags = LOCKFILE_EXCLUSIVE_LOCK
        if not windll.kernel32.LockFileEx(handle, flags, 0, 1, 0, _stub_overlapped):
            error_code = GetLastError()
            raise OSError(error_code, os.strerror(error_code))


elif _platform == "Linux":
    # "flock", which is a BSD-style simple file lock, is used instead of "lockf", which is
    # a wrapper over POSIX fcntl file lock, due to the fact that "flock" shares common behavior
    # with a Windows lock function LockFileEx. Both, flock and LockFileEx are applied to a file
    # descriptor (named "file handle" in Windows environments). At the same time, fcntl.lockf locks
    # pair (pid, inode) what effectively allows several file descriptors to be locked exclusively
    # assuming that they are owned by the same process and open the same file.
    # See: https://apenwarr.ca/log/20101213
    # See: https://man7.org/linux/man-pages/man2/flock.2.html
    # See: https://man7.org/linux/man-pages/man3/lockf.3.html
    import fcntl

    def try_lock_exclusively(fileno: int) -> bool:
        try:
            fcntl.flock(fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            if err.errno == 11:
                return False
            raise
        return True

    def try_lock_shared(fileno: int) -> bool:
        try:
            # See: https://man7.org/linux/man-pages/man2/flock.2.html
            fcntl.flock(fileno, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as err:
            if err.errno == 11:
                return False
            raise
        return True

    def downgrade_lock(fileno: int):
        """Transform exclusive lock to shared.

        See: https://man7.org/linux/man-pages/man2/fcntl.2.html
        A single process can hold only one type of lock on a file region;
        if a new lock is applied to an already-locked region,
        then the existing lock is converted to the new lock type.
        """
        assert try_lock_shared(fileno)

    def _wait_until_locked(fileno: int):
        fcntl.flock(fileno, fcntl.LOCK_EX)


else:
    raise RuntimeError("Unsupported OS")


_logger = logging.getLogger(__name__)


class FileLockDirectory:

    def __init__(self, dir_path: Path):
        dir_path.mkdir(parents=True, exist_ok=True)
        self._dir_path = dir_path

    @contextmanager
    def try_locked(self, name: str):
        with try_locked(self._dir_path / f'{name}.lock'):
            yield


@contextmanager
def try_locked(file: Path):
    _logger.info("%s: Try to lock exclusively", file)
    file.touch(exist_ok=True)
    try:
        with file.open("rb") as fd:
            if not try_lock_exclusively(fd.fileno()):
                raise AlreadyLocked(f"Can't lock {file}")
            _logger.info("%s: Locked exclusively", file)
            yield
    finally:
        _logger.info("%s: Lock is released", file)


@contextmanager
def wait_locked_exclusively(file: Path, timeout_sec: float):
    end_at = time.monotonic() + timeout_sec
    max_delay_msec = 250
    min_delay_msec = 100
    while True:
        _logger.debug("Try to lock %s exclusively...", file)
        file.touch(exist_ok=True)
        try:
            with file.open("rb") as fd:
                if try_lock_exclusively(fd.fileno()):
                    _logger.debug("%s locked exclusively", file)
                    yield
                    return
                _logger.debug("Lock of %s has failed", file)
                sec_left = end_at - time.monotonic()
                if sec_left <= 0:
                    raise AlreadyLocked(f"Can't lock {file} after {timeout_sec}")
                factor = sec_left / timeout_sec
                addition_msec = int(max_delay_msec * factor)
                delay_msec = random.randint(0, addition_msec) + min_delay_msec
                time.sleep(delay_msec / 1000)
        finally:
            _logger.debug("%s is released", file)


@contextmanager
def wait_until_locked(file: Path):
    _logger.debug("Try to lock %s exclusively and uninterruptedly ...", file)
    file.touch(exist_ok=True)
    try:
        with file.open("rb") as fd:
            _wait_until_locked(fd.fileno())
            _logger.debug("%s locked exclusively", file)
            yield
    finally:
        _logger.debug("%s is released", file)
