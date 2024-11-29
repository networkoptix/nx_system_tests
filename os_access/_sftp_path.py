# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import errno
import io
import logging
import os
import pathlib
import stat
from typing import Iterable
from typing import Sequence

from os_access._exceptions import NotEmpty
from os_access._path import DirEntry
from os_access._path import RemotePath
from os_access._path import _FileStat
from os_access._ssh_shell import Ssh

_logger = logging.getLogger(__name__)


class SftpPath(RemotePath):

    def __init__(self, ssh: Ssh, *parts):
        self._ssh: Ssh = ssh
        self._path = pathlib.PurePosixPath(*parts)
        if not self._path.is_absolute():
            raise ValueError('SftpPath must be absolute')

    def __fspath__(self):
        return os.fspath(self._path)

    def __hash__(self):
        return hash((self._ssh, self._path))

    def __eq__(self, other: 'SftpPath'):
        if not isinstance(other, SftpPath):
            return NotImplemented
        if other._ssh is not self._ssh:
            return NotImplemented
        return self._path == other._path

    def __lt__(self, other: 'SftpPath'):
        if not isinstance(other, SftpPath):
            return NotImplemented
        if other._ssh is not self._ssh:
            return NotImplemented
        return self._path < other._path

    @property
    def stem(self):
        return self._path.stem

    @property
    def parts(self) -> Sequence[str]:
        return self._path.parts

    def _with_parts(self, *parts):
        return SftpPath(self._ssh, *parts)

    def absolute(self):
        return self

    def is_absolute(self):
        return True

    def relative_to(self, other: 'SftpPath'):
        if self._ssh is not other._ssh:
            raise ValueError("Cannot compare paths from different machines")
        return self._path.relative_to(other._path)

    def _traverse_to_closest_ancestor(self):
        """Find closest existing ancestor, its stat and non-existing ancestors."""
        checked = self
        to_create = []
        while True:
            try:
                closest_stat = self._ssh._sftp().stat(str(checked))
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise
                to_create.append(checked)
                checked = checked.parent
                continue
            return checked, closest_stat, to_create

    def _closest_ancestor_error(self):
        """Raise an exception based on whether the closest existing ancestor is dir or not."""
        closest, closest_stat, _ = self.parent._traverse_to_closest_ancestor()
        if not stat.S_ISDIR(closest_stat.st_mode):
            return NotADirectoryError(errno.ENOTDIR, "closest ancestor is not a dir: {}".format(closest))
        assert closest != self.parent, "if parent were a dir, this wouldn't be called"
        return FileNotFoundError(errno.ENOENT, "closest ancestor: {}".format(closest))

    def mkdir(self, mode=0o777, parents=False, exist_ok=False):
        """Specific overload to handle poor error reporting in SFTP.

        mkdir in SFTP cannot distinguish between non-existent
        parent and parent which is not directory. That's why some additional
        checks are needed. To straighten the code, mkdir is rewritten on
        Path level.
        """
        checked, closest_stat, to_create = self._traverse_to_closest_ancestor()
        if not stat.S_ISDIR(closest_stat.st_mode):
            if checked == self:
                raise FileExistsError(errno.EEXIST, "exists, not a dir: {}".format(checked))
            raise NotADirectoryError(errno.ENOTDIR, "not a dir: {}".format(checked))
        if not to_create and not exist_ok:
            raise FileExistsError(errno.EEXIST, "exists: {}".format(self))
        if len(to_create) > 1 and not parents:
            raise FileNotFoundError(errno.ENOENT, "not found, would create: {}".format(to_create))
        while to_create:
            new_path = to_create.pop()
            self._ssh._sftp().mkdir(str(new_path), mode=mode)

    def _get_filename(self) -> str:
        transport = self._ssh._sftp().sock.transport
        client_ip, client_port = transport.sock.getpeername()
        user = transport.get_username()
        return f"sftp://{user}@{client_ip}:{client_port}{self}"

    def rename(self, other: RemotePath):
        try:
            return self._ssh._sftp().rename(str(self), str(other))
        except IOError as e:
            if e.errno == errno.ENOENT:
                raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
            raise

    def unlink(self, missing_ok=False):
        try:
            self._ssh._sftp().remove(str(self))
        except IOError as e:
            if e.errno is None or e.errno == errno.EISDIR:
                raise IsADirectoryError(e.errno, e.strerror)
            if e.errno == errno.ENOENT:
                if missing_ok:
                    return
                raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
            raise

    def stat(self):
        try:
            stat = self._ssh._sftp().stat(str(self))
        except IOError as e:
            if e.errno == errno.ENOENT:
                raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
            raise
        return _FileStat(stat.st_size, stat.st_mtime, stat.st_mode)

    def is_symlink(self) -> bool:
        return stat.S_ISLNK(self.stat().st_mode)

    def chmod(self, mode):
        try:
            return self._ssh._sftp().chmod(str(self), mode)
        except IOError as e:
            if e.errno == errno.ENOENT:
                raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
            raise

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if 'b' not in mode:
            raise ValueError(
                "Opening file in the text mode is not supported; "
                "use the binary mode or consider io.TextIOWrapper")
        try:
            f = self._ssh._sftp().open(str(self), mode, bufsize=buffering)
        except IOError as e:
            if 'w' in mode:
                if e.errno == errno.ENOENT:
                    raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
                if e.errno is None:
                    raise IsADirectoryError(errno.EISDIR, e.strerror)
                raise
            if 'r' in mode:
                if e.errno == errno.ENOENT:
                    raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
                if e.errno is None:
                    raise NotADirectoryError(errno.ENOTDIR, e.strerror)
                raise
            raise
        if stat.S_ISDIR(f.stat().st_mode):
            raise IsADirectoryError(errno.EISDIR, 'Probably a dir')
        return f

    def read_text(self, encoding='utf-8', errors='strict'):
        return self.read_bytes().decode(encoding=encoding, errors=errors)

    def read_bytes(self):
        buf = io.BytesIO()
        try:
            self._ssh._sftp().getfo(str(self), buf)
        except IOError as e:
            if e.errno is None or e.errno == errno.EISDIR:
                raise IsADirectoryError(e.errno, e.strerror, self._get_filename())
            if e.errno == errno.ENOENT:
                raise FileNotFoundError(e.errno, e.strerror, self._get_filename())
            raise
        buf.seek(0)
        return buf.getvalue()

    def write_text(self, data, encoding='utf-8', errors='strict'):
        return self.write_bytes(data.encode(encoding, errors))

    def write_bytes(self, data):
        buf = io.BytesIO(data)
        try:
            return self._ssh._sftp().putfo(buf, str(self), confirm=False)
        except IOError as write_exc:
            if write_exc.errno is None:  # SFTP as protocol never raises analogue of errno.EISDIR.
                raise IsADirectoryError(errno.EISDIR, f"is a dir: {self}")
            if write_exc.errno == errno.ENOENT:
                raise self._closest_ancestor_error()
            raise

    def _scandir(self) -> Iterable[DirEntry]:
        for attrs in self._ssh._sftp().listdir_attr(str(self)):
            yield DirEntry(
                attrs.filename,
                stat.S_ISDIR(attrs.st_mode),
                stat.S_ISLNK(attrs.st_mode),
                )

    def rmdir(self):
        try:
            return self._ssh._sftp().rmdir(str(self))
        except IOError as e:
            if e.errno is None or e.errno == errno.ENOTEMPTY:
                raise NotEmpty(e.errno, e.strerror)
            if e.errno == errno.EISDIR:
                raise IsADirectoryError(e.errno, e.strerror)
            if e.errno == errno.ENOTDIR:
                raise NotADirectoryError(e.errno, e.strerror)
            raise
