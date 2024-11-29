# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import stat
from abc import ABCMeta
from abc import abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Collection
from typing import Iterator
from typing import Sequence

from directories._create_time import create_time

_logger = logging.getLogger(__name__)


@lru_cache()
def get_run_dir() -> Path:
    work_dir = get_ft_artifacts_root() / 'work-dir'
    work_dir.mkdir(exist_ok=True)
    prefix = 'run_'
    now = create_time()
    pid = os.getpid()
    name = f'{prefix}{now:%Y%m%d_%H%M%S}_{pid}'
    run_dir = work_dir / name
    run_dir.mkdir(parents=False, exist_ok=False)
    _make_dir_link(run_dir, 'latest', work_dir)
    _logger.info("Run dir: %s", run_dir)
    return run_dir


def _make_dir_link(target: Path, name: str, base: Path):
    link = base / name
    try:
        link.unlink()
    except FileNotFoundError:
        pass
    if os.name == 'nt':
        import _winapi  # No such package on Linux  .
        _winapi.CreateJunction(str(target), str(link))
    else:
        try:
            link.symlink_to(target.relative_to(base), target_is_directory=True)
        except FileExistsError:
            # There can be many parallel processes on same host,
            # which can lead to this exception. Since "latest" symlink
            # is used primarily on local host with local runs,
            # this error can be safely ignored.
            pass


@lru_cache()
def get_ft_artifacts_root():
    root = Path('~/.cache/nxft-artifacts/').expanduser()
    root.parent.mkdir(exist_ok=True)
    root.mkdir(exist_ok=True)
    return root


@lru_cache()
def get_ft_snapshots_cache_root():
    root = Path('~/.cache/nxft-snapshots-download/').expanduser()
    root.parent.mkdir(exist_ok=True)
    root.mkdir(exist_ok=True)
    return root


@lru_cache()
def get_ft_snapshots_origin_root():
    root = Path('~/.cache/nxft-snapshots-origin/').expanduser()
    root.parent.mkdir(exist_ok=True)
    root.mkdir(exist_ok=True)
    return root


def list_entries(root: Path) -> Iterator['Entry']:
    """List entries in directory recursively.

    Use os.scandir() and single stat() call to speed up process.
    """
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            entries = os.scandir(current)
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                # entry.stat() returns different stat info than os.stat(entry.path).
                # st_ino, st_dev and timestamps are different.
                # To get the correct information os.stat() must be used.
                entry_stat = os.stat(entry.path, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(entry_stat.st_mode):
                stack.append(entry.path)
                yield _Directory(entry.path, entry_stat)
            elif stat.S_ISREG(entry_stat.st_mode):
                yield _File(entry.path, entry_stat)
            else:
                # Ignore other file types.
                pass


class EntryRoot(metaclass=ABCMeta):

    def __init__(self, root_directories: Collection[Path]):
        self._root_directories = root_directories

    def __repr__(self):
        return f"<{self.__class__.__name__} for {self._root_directories}>"

    @abstractmethod
    def list_entries(self) -> Sequence['Entry']:
        pass

    def total_size(self) -> int:
        return sum(e.size() for e in self.list_entries())


class Entry(metaclass=ABCMeta):

    def __init__(self, path: str, file_stat: os.stat_result):
        self._path = path
        self._stat = file_stat

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._path}>"

    def __eq__(self, other):
        if not isinstance(other, Entry):
            return NotImplemented
        return self._path == other._path

    @abstractmethod
    def used_at(self) -> float:
        pass

    @abstractmethod
    def modified_at(self) -> float:
        pass

    @abstractmethod
    def size(self) -> int:
        pass

    @abstractmethod
    def delete(self):
        pass

    def path(self) -> Path:
        return Path(self._path)


class _File(Entry):

    def delete(self):
        try:
            os.unlink(self._path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise CannotDeleteEntry(e)
        _logger.info("%s deleted", self)

    def size(self):
        return self._stat.st_size

    def used_at(self):
        return max(self._stat.st_atime, self._stat.st_mtime)

    def modified_at(self) -> float:
        return self._stat.st_mtime


class _Directory(Entry):

    def delete(self):
        try:
            os.rmdir(self._path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise CannotDeleteEntry(e)
        _logger.info("%s deleted", self)

    def size(self):
        return self._stat.st_size

    def used_at(self):
        return self._stat.st_mtime

    def modified_at(self) -> float:
        return self._stat.st_mtime


class CannotDeleteEntry(Exception):
    pass
