# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import errno
import logging
import os
import platform
import shutil
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from typing import Collection
from typing import Sequence

from arms.hierarchical_storage.qcow2disk import DiskExists
from arms.hierarchical_storage.qcow2disk import QCOW2ChildDisk

_max_percent_config = 'max_size_percent.cfg'
_disk_name = 'disk.qcow2'
_last_access_filename = 'last_access'
_tmp_prefix = 'tmp_'


if platform.system() == "Windows":
    def _wait_locked_exclusively(fd: int):
        raise NotImplementedError("Not implemented for Windows machines")

    def _try_lock(fd: int):
        raise NotImplementedError("Not implemented for Windows machines")

else:
    import fcntl

    def _wait_locked_exclusively(fd: int):
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _try_lock(fd: int):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            if err.errno == errno.EWOULDBLOCK:
                raise _AlreadyLocked()
            raise


class Disk(metaclass=ABCMeta):

    @abstractmethod
    def get_diff(self, name: str) -> 'DifferenceDisk':
        pass

    @abstractmethod
    def get_filesystem_path(self) -> Path:
        pass


class RootDisk(Disk, metaclass=ABCMeta):

    def prune(self):
        pass


class DifferenceDisk(Disk, metaclass=ABCMeta):

    @abstractmethod
    def create(self) -> 'LockedDisk':
        pass

    @abstractmethod
    def remove(self):
        pass

    @abstractmethod
    def rename(self, name: str) -> 'DifferenceDisk':
        pass


class LockedDisk(AbstractContextManager, metaclass=ABCMeta):

    @abstractmethod
    def unlock(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()


class PendingSnapshot:

    def __init__(self, parent_disk: Disk, descendant_name: str):
        self._descendant_name = descendant_name
        temp_snapshot_name = f'{_tmp_prefix}{descendant_name}'
        self._tmp_disk = parent_disk.get_diff(temp_snapshot_name)
        self._target = parent_disk.get_diff(descendant_name)
        try:
            self._locked_disk = self._tmp_disk.create()
        except (_AlreadyLocked, ChildExists):
            raise SnapshotAlreadyPending(f"{self._target} is being created")
        try:
            self._target.get_filesystem_path()
        except ChildNotExist:
            logging.info("%r: Created", self)
        else:
            self._tmp_disk.remove()
            raise ChildExists(f"{self._tmp_disk} exists")

    def rollback(self):
        logging.info("%r: Rollback", self)
        self._tmp_disk.remove()
        self._locked_disk.unlock()

    def commit(self):
        logging.info("%r: Commit", self)
        self._tmp_disk.rename(self._descendant_name)
        self._locked_disk.unlock()

    def get_filesystem_path(self):
        return self._tmp_disk.get_filesystem_path()

    def __repr__(self):
        return f'<Pending {self._target}>'


class QCOWRootDisk(RootDisk):

    def __init__(self, root_dir: Path):
        self._disk = root_dir / _disk_name
        if not self._disk.exists():
            raise RuntimeError(f"Can't find root disk {self._disk}")
        self._root_dir = root_dir
        self._allowed_percentage_file = _PercentFile(self._root_dir)

    def prune(self):
        volume = self._allowed_percentage_file.get_volume()
        _logger.info("%r: Prune to size %s", self, volume)
        with self._locked_root() as root_fd:
            for leaf in self._leafs_by_age(root_fd):
                try:
                    volume = leaf.fill(volume)
                except _VolumeFull:
                    _logger.info("%r: Remove %s due to size threshold", self, leaf)
                    try:
                        leaf.remove()
                    except _AlreadyLocked:
                        _logger.info("%r: Can't remove %s due to lock collision", self, leaf)

    def get_filesystem_path(self) -> Path:
        return self._disk

    def get_diff(self, name: str) -> 'DifferenceDisk':
        return QCOWDifferenceDisk(self._root_dir, [name])

    @contextmanager
    def _locked_root(self) -> AbstractContextManager[int]:
        with _closed(_ensure_locked_directory(self._root_dir)) as locked_fd:
            yield locked_fd

    def _leafs_by_age(self, parent_fd: int) -> Sequence['_DiskLeaf']:
        result = []
        for path, dir_names, _file_names in os.walk(self._root_dir):
            disk_path = path + os.path.sep + _disk_name
            if dir_names:
                _logger.debug("%s: %s is not a leaf disk: %s", self, disk_path, dir_names)
                continue
            try:
                disk_stat = os.stat(disk_path, dir_fd=parent_fd)
            except FileNotFoundError:
                _logger.warning("%s: %s does not contain disk file %s", self, disk_path, _disk_name)
                continue
            last_usage_time = max(disk_stat.st_atime, disk_stat.st_mtime)
            result.append((path, disk_stat.st_size, last_usage_time))
        youngest_leafs_first = sorted(result, key=lambda d: d[2], reverse=True)
        return [_DiskLeaf(path, st_size) for path, st_size, _usage_time in youngest_leafs_first]

    def __repr__(self):
        return f'<Root disk: {self._disk}>'


class _PercentFile:

    def __init__(self, directory: Path):
        self._path = directory / _max_percent_config

    def get_volume(self) -> '_Volume':
        try:
            disk_stat = shutil.disk_usage(self._path)
        except FileNotFoundError:
            _logger.info("By size usage is disabled for %s", self._path)
            return _UncappedVolume()
        volume_capacity = disk_stat.free + disk_stat.used
        try:
            size_threshold_percent = float(self._path.read_text().strip())
        except FileNotFoundError:
            _logger.info("By size usage is disabled for %s", self._path)
            return _UncappedVolume()
        return _CappedVolume(int(volume_capacity * size_threshold_percent / 100))

    def set_value(self, value: float):
        self._path.write_text(f'{value:.3f}\n')


class _DiskLeaf:

    def __init__(self, path: str, size_bytes: int):
        self._path = path
        self._size_bytes = size_bytes

    def remove(self):
        try:
            dir_fd = os.open(self._path, flags=os.O_RDONLY | os.O_DIRECTORY)
        except FileNotFoundError:
            _logger.debug("%r: Already removed", self)
            return
        with _closed(dir_fd):
            _try_lock(dir_fd)
            shutil.rmtree(self._path, dir_fd=dir_fd)
        _logger.debug("%r: Removed", self)

    def fill(self, volume: '_Volume') -> '_Volume':
        return volume.fill(self._size_bytes)

    def __repr__(self):
        size_gb = self._size_bytes / 1024 / 1024 / 1024
        return f'<Leaf {self._path}, {size_gb:.3f} GB>'


class _Volume(metaclass=ABCMeta):

    @abstractmethod
    def fill(self, size_bytes: int) -> '_Volume':
        pass


class _UncappedVolume(_Volume):

    def __init__(self):
        self._used_bytes = 0

    def fill(self, size_bytes):
        volume = self.__class__()
        volume._used_bytes = self._used_bytes + size_bytes
        return volume

    def __repr__(self):
        return f'<InfiniteVolume {self._used_bytes}>'


class _CappedVolume(_Volume):

    def __init__(self, size_bytes: int):
        self._size_bytes = size_bytes
        self._used_bytes = 0

    def fill(self, size_bytes):
        new_used_bytes = self._used_bytes + size_bytes
        if new_used_bytes > self._size_bytes:
            raise _VolumeFull()
        volume = self.__class__(self._size_bytes)
        volume._used_bytes = new_used_bytes
        return volume

    def _free_percent(self) -> float:
        return (1 - self._used_bytes / self._size_bytes) * 100

    def __repr__(self):
        return f'<Volume {self._free_percent():.3f}% free>'


class _VolumeFull(Exception):
    pass


class QCOWDifferenceDisk(DifferenceDisk):

    def __init__(self, root_directory: Path, stems: Sequence[str]):
        self._root_dir = root_directory
        self._stems = stems
        self._disk_dir = self._root_dir.joinpath(*stems)
        self._disk = self._disk_dir / _disk_name

    def create(self):
        # Creation of a disk is a non-atomic operation.
        # TODO: Find the way to avoid the global lock.
        with self._locked_root():
            try:
                self._disk_dir.mkdir(exist_ok=True)
            except FileNotFoundError:
                raise ParentNotExist(f"{self} parent not exist")
            fd = _try_locked_directory(self._disk_dir)
            qcow_disk = QCOW2ChildDisk(self._disk, Path(f'../{_disk_name}'))
            try:
                qcow_disk.create()
            except DiskExists:
                raise ChildExists()
            return _LockedDiskDirectory(fd, f"Root: {self._root_dir}")

    def remove(self):
        if children := self._get_children():
            raise HasChildren(f"{self} has children {children}")
        shutil.rmtree(self._disk_dir, ignore_errors=True)
        logging.info("%r: Removed", self)

    def get_filesystem_path(self):
        if not self._disk.exists():
            raise ChildNotExist(f"{self} not exist")
        return self._disk

    def get_diff(self, name: str):
        return QCOWDifferenceDisk(self._root_dir, [*self._stems, name])

    def rename(self, name):
        target = self._disk_dir.with_name(name)
        try:
            self._disk_dir.rename(target)
        except FileNotFoundError:
            raise ChildNotExist(f"{self} not exist")
        return QCOWDifferenceDisk(self._root_dir, [*self._stems[:-1], name])

    def _get_children(self) -> Collection[str]:
        try:
            return [file.name for file in self._disk_dir.iterdir() if file.is_dir()]
        except FileNotFoundError:
            return []

    @contextmanager
    def _locked_root(self) -> AbstractContextManager[None]:
        with _closed(_ensure_locked_directory(self._root_dir)):
            yield

    def __repr__(self):
        return f'<Child {self._disk}>'


class _LockedDiskDirectory(LockedDisk):

    def __init__(self, locked_fd: int, _repr: str):
        self._repr = _repr
        self._locked_fd = locked_fd

    def unlock(self):
        os.close(self._locked_fd)

    def __repr__(self):
        return f'<Locked {self._repr}>'


@contextmanager
def _closed(fd: int) -> AbstractContextManager[int]:
    try:
        yield fd
    finally:
        os.close(fd)


def _ensure_locked_directory(path: Path) -> int:
    # Pathlib does not allow opening a directory via Path.open().
    dir_fd = os.open(path, flags=os.O_RDONLY | os.O_DIRECTORY)
    _wait_locked_exclusively(dir_fd)
    return dir_fd


def _try_locked_directory(path: Path) -> int:
    # Pathlib does not allow opening a directory via Path.open().
    dir_fd = os.open(path, flags=os.O_RDONLY | os.O_DIRECTORY)
    _try_lock(dir_fd)
    return dir_fd


class ParentNotExist(Exception):
    pass


class HasChildren(Exception):
    pass


class ChildExists(Exception):
    pass


class ChildNotExist(Exception):
    pass


class SnapshotAlreadyPending(Exception):
    pass


class _AlreadyLocked(Exception):
    pass


_logger = logging.getLogger(__name__)
