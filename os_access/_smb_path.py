# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import functools
import io
import logging
import os
import stat
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from ipaddress import IPv4Address
from pathlib import PureWindowsPath
from socket import SHUT_RDWR
from typing import Iterable

from smb import SMBConnection
from smb import smb_structs
from smb.base import NotConnectedError
from smb.base import SMBTimeout

from os_access._exceptions import CannotDelete
from os_access._exceptions import NotEmpty
from os_access._path import DirEntry
from os_access._path import RemotePath
from os_access._path import _FileStat

_logger = logging.getLogger(__name__)

# See: https://msdn.microsoft.com/en-us/library/cc704588.aspx
_STATUS_SUCCESS = 0x00000000
_STATUS_NO_SUCH_FILE = 0xC000000F
_STATUS_OBJECT_NAME_NOT_FOUND = 0xC0000034
_STATUS_OBJECT_NAME_COLLISION = 0xC0000035
_STATUS_OBJECT_PATH_NOT_FOUND = 0xC000003A
_STATUS_NOT_A_DIRECTORY = 0xC0000103
_STATUS_FILE_IS_A_DIRECTORY = 0xC00000BA
_STATUS_SHARING_VIOLATION = 0xC0000043
_STATUS_DELETE_PENDING = 0xC0000056
_STATUS_DIRECTORY_NOT_EMPTY = 0xC0000101
_STATUS_REQUEST_NOT_ACCEPTED = 0xC00000D0
_STATUS_ACCESS_DENIED = 0xC0000022
_STATUS_USER_SESSION_DELETED = 0xC0000203
_STATUS_NETWORK_NAME_DELETED = 0xC00000C9
_STATUS_CANNOT_DELETE = 0xC0000121

_status_to_errno = {
    _STATUS_NO_SUCH_FILE: errno.ENOENT,
    _STATUS_OBJECT_NAME_NOT_FOUND: errno.ENOENT,
    _STATUS_OBJECT_PATH_NOT_FOUND: errno.ENOENT,
    _STATUS_OBJECT_NAME_COLLISION: errno.EEXIST,
    _STATUS_NOT_A_DIRECTORY: errno.ENOTDIR,
    _STATUS_FILE_IS_A_DIRECTORY: errno.EISDIR,
    _STATUS_ACCESS_DENIED: errno.EACCES,
    _STATUS_SHARING_VIOLATION: 32,  # Same as if Python cannot delete file on Windows.
    _STATUS_DELETE_PENDING: errno.EWOULDBLOCK,
    _STATUS_DIRECTORY_NOT_EMPTY: errno.ENOTEMPTY,
    _STATUS_REQUEST_NOT_ACCEPTED: errno.EPERM,
    _STATUS_CANNOT_DELETE: errno.EBUSY,
    }


def _extract_error_status(e: smb_structs.OperationFailure):
    for message in reversed(e.smb_messages):
        if message.status != _STATUS_SUCCESS:
            return message.status
    raise AssertionError("Cannot get OperationFailure with any error status")


def _reraising_on_operation_failure(status_to_error_cls):
    def decorator(func):
        @functools.wraps(func)
        def decorated(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except smb_structs.OperationFailure as e:
                _store_smb_messages(e)
                last_message_status = _extract_error_status(e)
                if last_message_status in status_to_error_cls:
                    error_cls = status_to_error_cls[last_message_status]
                    raise error_cls(_status_to_errno[last_message_status], e.message)
                raise
            except smb_structs.ProtocolError as e:
                if e.smb_message.status != _STATUS_REQUEST_NOT_ACCEPTED:
                    raise
                raise RequestNotAccepted()

        return decorated

    return decorator


_reraise_for_existing = _reraising_on_operation_failure({
    _STATUS_DIRECTORY_NOT_EMPTY: NotEmpty,
    _STATUS_OBJECT_NAME_NOT_FOUND: FileNotFoundError,
    _STATUS_OBJECT_PATH_NOT_FOUND: FileNotFoundError,
    _STATUS_FILE_IS_A_DIRECTORY: IsADirectoryError,
    _STATUS_SHARING_VIOLATION: PermissionError,
    _STATUS_CANNOT_DELETE: CannotDelete,
    })
_reraise_for_new = _reraising_on_operation_failure({
    _STATUS_FILE_IS_A_DIRECTORY: IsADirectoryError,
    _STATUS_OBJECT_PATH_NOT_FOUND: FileNotFoundError,
    _STATUS_OBJECT_NAME_COLLISION: FileExistsError,
    })


def _retrying_on_status(*statuses):
    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            started_at = time.monotonic()
            while True:
                try:
                    return func(*args, **kwargs)
                except smb_structs.OperationFailure as e:
                    _store_smb_messages(e)
                    last_message_status = _extract_error_status(e)
                    if last_message_status not in statuses:
                        raise
                    if time.monotonic() - started_at > 5:
                        raise
                time.sleep(2)

        return decorated

    return decorator


def _reconnect_and_retry(method):
    """Reconnect and retry on a recoverable error.

    Cope with
    STATUS_USER_SESSION_DELETED and
    STATUS_NETWORK_NAME_DELETED

    The error 0xC0000203 (STATUS_USER_SESSION_DELETED)
    may appear when local system time on remote machine is changed.

    The error 0xC00000C9 (STATUS_NETWORK_NAME_DELETED)
    appears if volume was re-mounted.

    By now, there are no known methods to work around these problems
    other than a simple reconnect.
    """
    @functools.wraps(method)
    def decorated_method(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ConnectionResetError:
            _logger.warning("ConnectionResetError, reconnect and retry.")
        except NotConnectedError:
            _logger.warning("Connection was closed, reconnect and retry.")
        except smb_structs.OperationFailure as e:
            _store_smb_messages(e)
            error_status = _extract_error_status(e)
            if error_status not in [_STATUS_USER_SESSION_DELETED, _STATUS_NETWORK_NAME_DELETED]:
                raise
            _logger.warning(f"Got {error_status}, reconnect and retry.")
        except SMBTimeout:
            # In some cases, particularly after reconfiguring the network
            # (for example, after using setup_flat_network()), the SMB connection
            # may become unresponsive.
            _logger.warning("The SMB connection has timed out, reconnect and retry.")
        self._connection_pool.close()
        return method(self, *args, **kwargs)

    return decorated_method


def _reconnect_and_retry_on_connection_error(method):
    @functools.wraps(method)
    def decorated(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except NotConnectedError:
            _logger.warning("Smb not connected. Connect and retry.")
            self._connection_pool.close()
        return method(self, *args, **kwargs)

    return decorated


class RequestNotAccepted(Exception):
    message = (
        "No more connections can be made to this remote computer at this time"
        " because the computer has already accepted the maximum number of connections.")

    def __init__(self):
        super(RequestNotAccepted, self).__init__(self.message)


class _SmbConnectionPool:

    def __init__(self, username, password, address, port):
        self._username = username  # str
        self._password = password  # str
        self._address: IPv4Address = address
        self._port = port  # type: int
        self._lock = threading.Lock()
        self._connection = None

    def __repr__(self):
        return '<SMBConnection {!s}:{:d}>'.format(self._address, self._port)

    def close(self):
        with self._lock:
            if self._connection is None:
                return
            try:
                self._connection.sock.shutdown(SHUT_RDWR)
            except OSError as e:
                if e.errno == 107:
                    _logger.warning("Socket seems to be closed on remote.")
                else:
                    raise e
            finally:
                self._connection.close()
                self._connection = None

    @contextmanager
    def connection_acquired(self):
        with self._lock:
            if self._connection is None:
                self._connection = self._open_connection()
            yield self._connection

    @_reraising_on_operation_failure({})
    def _open_connection(self):
        _logger.debug("Open connection")
        client_name = 'FUNC_TESTS_EXECUTION'  # Arbitrary ASCII string.
        server_name = 'dummy'  # Not used because SMB runs over TCP directly. But must not be empty.
        connection = SMBConnection.SMBConnection(
            self._username, self._password,
            client_name, server_name, is_direct_tcp=True)
        try:
            auth_succeeded = connection.connect(
                str(self._address), port=self._port, timeout=10)
        except SMBTimeout:  # This happens rarely on Windows 8.1
            _logger.debug("Fail connecting to SMB server; Retry")
            auth_succeeded = connection.connect(
                str(self._address), port=self._port)
        if not auth_succeeded:
            raise RuntimeError("Auth failed")
        return connection


class SmbPath(RemotePath):

    def __init__(self, connection_pool: _SmbConnectionPool, *parts: str):
        self._connection_pool = connection_pool
        self._path = PureWindowsPath(*parts)
        if not self._path.is_absolute():
            raise ValueError('SmbPath must be absolute')
        self._tree = self._path.drive[0] + '$'
        self._filename = '\\'.join(self._path.parts[1:])

    def __fspath__(self):
        return os.fspath(self._path)

    def __hash__(self):
        return hash((self._connection_pool, self._path))

    def __eq__(self, other: 'SmbPath'):
        if not isinstance(other, SmbPath):
            return NotImplemented
        if other._connection_pool is not self._connection_pool:
            return NotImplemented
        return self._path == other._path

    def __lt__(self, other: 'SmbPath'):
        if not isinstance(other, SmbPath):
            return NotImplemented
        if other._connection_pool is not self._connection_pool:
            return NotImplemented
        return self._path < other._path

    @property
    def stem(self):
        return self._path.stem

    @property
    def parts(self):
        return self._path.parts

    def _with_parts(self, *parts):
        return SmbPath(self._connection_pool, *parts)

    def absolute(self):
        return self

    def is_absolute(self):
        return True

    def relative_to(self, other: 'SmbPath'):
        if self._connection_pool is not other._connection_pool:
            raise ValueError("Cannot compare paths from different machines")
        return self._path.relative_to(other._path)

    @_reconnect_and_retry
    @_reraise_for_existing
    def stat(self):
        with self._connection_pool.connection_acquired() as conn:
            attrs = conn.getAttributes(self._tree, self._filename)
        st_mode = stat.S_IFDIR if attrs.isDirectory else stat.S_IFREG
        st_size = attrs.file_size
        st_mtime = int(attrs.last_write_time)
        return _FileStat(st_size, st_mtime, st_mode)

    lstat = stat

    def is_symlink(self):
        return False

    @_reconnect_and_retry
    @_reraise_for_existing
    def _scandir(self) -> Iterable[DirEntry]:
        with self._connection_pool.connection_acquired() as conn:
            try:
                shared_files = [*conn.listPath(self._tree, self._filename)]
            except smb_structs.OperationFailure as err:
                _store_smb_messages(err)
                if 'Path not found' in err.message:
                    raise FileNotFoundError(self._path)
                raise
        result = []
        for shared_file in shared_files:
            if shared_file.filename not in ('.', '..'):
                result.append(DirEntry(
                    shared_file.filename,
                    shared_file.isDirectory,
                    False,
                    ))
        return result

    @_reconnect_and_retry
    @_reraise_for_existing
    def rmdir(self):
        with self._connection_pool.connection_acquired() as conn:
            conn.deleteDirectory(self._tree, self._filename)

    @_reconnect_and_retry
    @_reraise_for_existing  # The source is considered existing.
    @_reraise_for_new  # The destination is considered new.
    def rename(self, new_path: 'SmbPath'):
        assert new_path._tree == self._tree
        with self._connection_pool.connection_acquired() as conn:
            return conn.rename(self._tree, self._filename, new_path._filename)

    def _traverse_to_closest_ancestor(self):
        cur = self
        traversed = []
        not_found_statuses = {
            _STATUS_OBJECT_NAME_NOT_FOUND,
            _STATUS_OBJECT_PATH_NOT_FOUND}
        while True:
            try:
                with self._connection_pool.connection_acquired() as conn:
                    attrs = conn.getAttributes(cur._tree, cur._filename)
            except smb_structs.OperationFailure as e:
                _store_smb_messages(e)
                error_status = _extract_error_status(e)
                if error_status not in not_found_statuses:
                    raise
                traversed.append(cur)
                cur = cur.parent
                continue
            return cur, attrs, traversed

    @_reconnect_and_retry
    def mkdir(self, mode=None, parents=False, exist_ok=False):
        # TODO: Code is originally for SFTP. Could it be simpler for SMB?
        if mode is not None:
            _logger.warning("`mode` is ignored but given: %r", mode)
        closest, closest_attrs, to_create = self._traverse_to_closest_ancestor()
        if not closest_attrs.isDirectory:
            if closest == self:
                raise FileExistsError(errno.EEXIST, "exists, not a dir: {}".format(closest))
            raise NotADirectoryError(errno.ENOTDIR, "not a dir: {}".format(closest))
        if not to_create and not exist_ok:
            raise FileExistsError(errno.EEXIST, "exists: {}".format(self))
        if len(to_create) > 1 and not parents:
            raise FileNotFoundError(errno.ENOENT, "not found, would create: {}".format(to_create))
        while to_create:
            new_path = to_create.pop()
            with self._connection_pool.connection_acquired() as conn:
                conn.createDirectory(new_path._tree, new_path._filename)

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if mode != 'rb+':
            raise NotImplementedError(
                "Only the rb+ mode is supported at the moment. "
                "This method only pretends and mimics the real open(). "
                "pySMB doesn't supports opening a file. "
                "The SMB protocol does - as the CREATE request.")
        return _SmbOpen(self)

    @_reconnect_and_retry
    @_reconnect_and_retry_on_connection_error
    @_reraise_for_existing
    @_retrying_on_status(_STATUS_SHARING_VIOLATION)
    def read_bytes(self):
        buffer = io.BytesIO()
        with self._connection_pool.connection_acquired() as conn:
            conn.retrieveFile(self._tree, self._filename, buffer)
        return buffer.getvalue()

    @_reconnect_and_retry
    @_retrying_on_status(_STATUS_DELETE_PENDING, _STATUS_SHARING_VIOLATION)
    def write_bytes(self, data):
        ad_hoc_file_object = io.BytesIO(data)
        try:
            with self._connection_pool.connection_acquired() as conn:
                try:
                    return conn.storeFile(self._tree, self._filename, ad_hoc_file_object)
                except SMBTimeout:
                    time.sleep(0.5)
                    _logger.debug("Fail writing a file to SMB server; Retry")
                    return conn.storeFile(self._tree, self._filename, ad_hoc_file_object)
        except smb_structs.OperationFailure as write_exc:
            _store_smb_messages(write_exc)
            status = _extract_error_status(write_exc)
            if status == _STATUS_FILE_IS_A_DIRECTORY:
                raise IsADirectoryError(errno.EISDIR, f"is a dir: {self}")
            if status == _STATUS_OBJECT_PATH_NOT_FOUND:
                closest, closest_attrs, _ = self.parent._traverse_to_closest_ancestor()
                if not closest_attrs.isDirectory:
                    raise NotADirectoryError(errno.ENOTDIR, "closes ancestor is not a dir: {}".format(closest))
                raise FileNotFoundError(errno.ENOENT, "closest ancestor: {}".format(closest))
            raise

    @_reraise_for_new
    def read_text(self, encoding='utf8', errors='strict'):
        data = self.read_bytes()
        text = data.decode(encoding=encoding, errors=errors)
        return text

    @_reraise_for_new
    def write_text(self, text, encoding='utf8', errors='strict'):
        data = text.encode(encoding=encoding, errors=errors)
        bytes_written = self.write_bytes(data)
        assert bytes_written == len(data)
        return len(text)

    @_reconnect_and_retry
    @_reraise_for_existing
    @_retrying_on_status(_STATUS_SHARING_VIOLATION)  # Let OS and processes time unlock files.
    def unlink(self, missing_ok=False):
        # After 1.2.1 pysmb deleteFiles has stopped raising FileNotFoundError
        # which our code relies upon. We won't fix pysmb because it takes a lot of time to
        # write a specific patch adding a method raising a FileNotFoundError exception.
        # Moreover, it is not guaranteed that the patch would be accepted by the author
        # who seems to have the package nearly abandoned.
        # Rollback to 1.1.27 pysmb is also not an option because it has a flawed md4 implementation
        # what prevents it from running on tls 3.0+ linux installations.
        win10_error = 'Path not found'
        win2019_error = 'Unable to open remote file object'
        with self._connection_pool.connection_acquired() as conn:  # type: SMBConnection.SMBConnection
            # Let just check a path before actual removal and raise an appropriate exception.
            try:
                conn.getAttributes(self._tree, self._filename)
            except smb_structs.OperationFailure as err:
                _store_smb_messages(err)
                if win10_error in err.message or win2019_error in err.message:
                    if missing_ok:
                        return
                    path_str = f"{self._tree[0]}:\\{self._filename}"
                    raise FileNotFoundError(path_str)
                raise
            return conn.deleteFiles(self._tree, self._filename)


class _SmbOpen:

    def __init__(self, path: SmbPath):
        self._connection_pool = path._connection_pool
        self._tree = path._tree
        self._filename = path._filename
        self._opened = False
        self._offset = 0

    def __enter__(self):
        self._opened = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._opened = False

    def seek(self, offset: int):
        self._offset = offset

    @_reconnect_and_retry
    @_reraise_for_new
    def read(self, size=-1) -> bytes:
        if not self._opened:
            raise ValueError('I/O operation on closed file.')
        # Only small lengths are expected, so no hacks here.
        ad_hoc_file_object = io.BytesIO()
        with self._connection_pool.connection_acquired() as conn:
            _attributes, bytes_read = conn.retrieveFileFromOffset(
                self._tree, self._filename, ad_hoc_file_object,
                offset=self._offset, max_length=size)
        data = ad_hoc_file_object.getvalue()
        assert bytes_read == len(data)
        return data

    @_reconnect_and_retry
    @_reraise_for_new
    @_retrying_on_status(_STATUS_DELETE_PENDING, _STATUS_SHARING_VIOLATION)
    def write(self, data: bytes) -> int:
        if not self._opened:
            raise ValueError('I/O operation on closed file.')
        ad_hoc_file_object = io.BytesIO(data)
        with self._connection_pool.connection_acquired() as conn:
            return conn.storeFileFromOffset(
                self._tree, self._filename, ad_hoc_file_object,
                offset=self._offset)


def _store_smb_messages(smb_exception: smb_structs.OperationFailure):
    # smb_exception.smb_messages contains references to the SMB messages in the common buffer
    # inside the pysmb library. Later, the messages are replaced by other messages, and the wrong
    # SMB messages are written to the logs.
    smb_exception.smb_messages = deepcopy(smb_exception.smb_messages)
