# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import errno
import logging
import os
import pathlib
import posixpath
import stat
import sys
from abc import abstractmethod
from fnmatch import fnmatch
from typing import Iterable
from typing import NamedTuple
from typing import Sequence
from typing import Tuple

_logger = logging.getLogger(__name__)


class _FileStat(NamedTuple):
    st_size: int
    st_mtime: int
    st_mode: int


class RemotePath(os.PathLike):

    def __repr__(self):
        return f'<{self.__class__.__name__ } {self}>'

    def __str__(self):
        return os.fspath(self)

    def __truediv__(self, other) -> RemotePath:
        return self._with_parts(*self.parts, other)

    @abstractmethod
    def __lt__(self, other: 'RemotePath'):
        pass

    def joinpath(self, *parts) -> RemotePath:
        return self._with_parts(*self.parts, *parts)

    @property
    def name(self) -> str:
        return self.parts[-1]

    @property
    def parent(self) -> RemotePath:
        return self._with_parts(*self.parts[:-1])

    @abstractmethod
    def relative_to(self, other) -> pathlib.PurePath:
        pass

    @property
    def suffix(self) -> str:
        [_, suffix] = posixpath.splitext(self)
        return suffix

    def with_suffix(self, suffix) -> RemotePath:
        [*path, name] = self.parts
        [stem, _] = posixpath.splitext(name)
        return self._with_parts(*path, stem + suffix)

    @property
    @abstractmethod
    def parts(self) -> Sequence[str]:
        pass

    @abstractmethod
    def _with_parts(self, *parts):
        pass

    @abstractmethod
    def absolute(self) -> RemotePath:
        pass

    @abstractmethod
    def is_absolute(self) -> bool:
        pass

    def exists(self):
        try:
            self.stat()
        except FileNotFoundError:
            return False
        return True

    @abstractmethod
    def unlink(self, missing_ok=False):
        pass

    def glob(self, pattern: str):
        if not pattern:
            raise ValueError(f"Unacceptable pattern: {pattern}")
        if '**' in pattern:
            raise NotImplementedError("Recursion is supported by .rglob()")
        if '/' in pattern or '\\' in pattern:
            raise NotImplementedError("Directories are unsupported")
        try:
            entries = [*self._scandir()]
        except (FileNotFoundError, NotADirectoryError):
            return []
        result = []
        for entry in entries:
            if _glob(pattern, entry.name):
                result.append(self / entry.name)
        return result

    def rglob(self, pattern: str) -> 'Iterable[RemotePath]':
        if not pattern:
            raise ValueError(f"Unacceptable pattern: {pattern}")
        if '/' in pattern or '\\' in pattern:
            raise NotImplementedError("Directories are unsupported")
        result = []
        for path, entry in self._walk(strict=False):
            if _glob(pattern, entry.name):
                result.append(path)
        return result

    def _walk(self, strict=True) -> 'Iterable[Tuple[RemotePath, DirEntry]]':
        try:
            entries = [*self._scandir()]
        except (FileNotFoundError, NotADirectoryError):
            if not strict:
                return
            raise
        for entry in entries:
            path = self / entry.name
            yield path, entry
            if entry.is_dir():
                yield from path._walk()

    def rmtree(self, ignore_errors=False, onerror=None, _check_symlink=True):
        """Recursively delete a directory tree.

        If ignore_errors is set, errors are ignored; otherwise, if onerror
        is set, it is called to handle the error with arguments (func,
        path, exc_info) where func is os.listdir, os.remove, or os.rmdir;
        path is the argument to that function that caused it to fail; and
        exc_info is a tuple returned by sys.exc_info().  If ignore_errors
        is false and onerror is None, an exception is raised.

        """
        _logger.debug("Remove dir tree: %s", self)
        if ignore_errors:
            def onerror(*_args):
                pass
        try:
            if _check_symlink and self.is_symlink():
                # symlinks to directories are forbidden, see bug #1669
                raise OSError("Cannot call rmtree on a symbolic link")
        except OSError:
            if onerror is None:
                raise
            onerror(self.is_symlink, self, sys.exc_info())
            # can't continue even if onerror hook returns
            return
        entries = []
        try:
            entries = list(self._scandir())
        except OSError:
            if onerror is None:
                raise
            onerror(self._scandir, self, sys.exc_info())
        for entry in entries:
            if entry.is_dir() and not entry.is_symlink():
                child = self / entry.name
                child.rmtree(
                    ignore_errors=ignore_errors,
                    onerror=onerror,
                    _check_symlink=False,
                    )
            else:
                child = self / entry.name
                try:
                    child.unlink()
                except OSError:
                    if onerror is None:
                        raise
                    onerror(child.unlink, child, sys.exc_info())
        try:
            self.rmdir()
        except OSError:
            if onerror is None:
                raise
            onerror(self.rmdir, self, sys.exc_info())

    def size(self):
        path_stat = self.stat()
        if not stat.S_ISREG(path_stat.st_mode):
            raise IsADirectoryError(errno.EISDIR, "Stat: {}".format(path_stat))
        return path_stat.st_size

    def is_dir(self):
        return self.stat().st_mode & stat.S_IFDIR

    @abstractmethod
    def is_symlink(self) -> bool:
        pass

    @abstractmethod
    def stat(self) -> _FileStat:
        pass

    def take_from(self, local_source_path):
        destination = self / local_source_path.name
        if not local_source_path.exists():
            raise FileNotFoundError(
                "Local file {} doesn't exist.".format(local_source_path))
        if destination.exists():
            return destination
        copy_file(local_source_path, destination)
        return destination

    @abstractmethod
    def open(self, mode='r'):
        pass

    @abstractmethod
    def read_text(self, encoding='utf-8', errors='strict') -> str:
        pass

    @abstractmethod
    def read_bytes(self) -> bytes:
        pass

    @abstractmethod
    def write_text(self, data: str, encoding='utf-8', errors='strict'):
        pass

    @abstractmethod
    def write_bytes(self, data: bytes):
        pass

    def iterdir(self):
        return [self / entry.name for entry in self._scandir()]

    @abstractmethod
    def _scandir(self) -> 'Iterable[DirEntry]':
        pass

    @abstractmethod
    def mkdir(self, parents=False, exist_ok=False):
        pass

    @abstractmethod
    def rmdir(self):
        pass

    @abstractmethod
    def rename(self, other: RemotePath):
        pass

    @property
    @abstractmethod
    def stem(self) -> str:
        pass


def _glob(pattern: str, filename: str):
    if filename.startswith('.') and not pattern.startswith('.'):
        return False
    return fnmatch(filename, pattern)


class DirEntry(NamedTuple):
    name: str
    is_dir_value: bool
    is_symlink_value: bool

    def is_dir(self):
        return self.is_dir_value

    def is_symlink(self):
        return self.is_symlink_value


def copy_file(source, destination):
    _logger.info("Copy from %s to %s", source, destination)
    destination.write_bytes(source.read_bytes())
