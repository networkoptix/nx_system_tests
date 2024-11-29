# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import tzinfo
from pathlib import PurePath
from pathlib import PurePosixPath
from typing import Sequence
from typing import Union

from installation._video_archive import ArchiveDirectory
from os_access import OsAccess
from os_access import RemotePath


class RemoteDirectory(ArchiveDirectory):

    def __init__(self, directory: RemotePath, os_access: OsAccess):
        self._dir = directory
        self._os_access = os_access

    def __repr__(self):
        return f'<{self.__class__.__name__} on {self._os_access!r} at {self._dir!r}>'

    def new_facade(self, folder_names: Sequence[str]) -> 'RemoteDirectory':
        new_path = self._dir.joinpath(*folder_names)
        return RemoteDirectory(new_path, self._os_access)

    def with_name(self, folder_name: str) -> 'RemoteDirectory':
        new_path = self._dir.parent.joinpath(folder_name)
        if not new_path.exists():
            new_path.mkdir()
        return RemoteDirectory(new_path, self._os_access)

    def exchange_contents(self, other: 'ArchiveDirectory') -> None:
        assert isinstance(other, RemoteDirectory)
        tmp_dir = self._dir.parent / 'aux_folder'
        _rename(self._dir, tmp_dir)
        _rename(other._dir, self._dir)
        _rename(tmp_dir, other._dir)

    def search_file_recursively(self, subdir: Union[str, PurePosixPath], rglob_pattern: str) -> Sequence[PurePath]:
        return [c.relative_to(self._dir) for c in self._dir.joinpath(subdir).rglob(rglob_pattern)]

    def write_file(self, path_parts: PurePosixPath, contents: bytes) -> None:
        path = self._dir.joinpath(path_parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    def create_fake_file(self, path_parts: PurePosixPath, file_size: int) -> None:
        path = self._dir.joinpath(path_parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._os_access.create_file(path, file_size)

    def file_exists(self, subpath: str) -> bool:
        return (self._dir / subpath).exists()

    def get_parent(self) -> str:
        return str(self._dir.parent)

    def unlink_file(self, path: PurePath) -> None:
        self._dir.joinpath(path).unlink()

    def remove_dir(self) -> None:
        _logger.debug("Remove dir %s", self._dir)
        self._dir.rmtree(ignore_errors=True)

    def files_size_sum_bytes(self, extension: str) -> int:
        if not self._dir.exists():
            return 0
        return self._os_access.files_size_sum(self._dir, extension)

    def get_timezone(self) -> tzinfo:
        return self._os_access.get_datetime().tzinfo


def _rename(dir_one, dir_two):
    """Wait for all files in the specified SMB directory to be released.

    Continuously check the directory, ensuring that no files are locked or in use,
    particularly after subsequent renaming operations within the networked environment.
    """
    timeout_sec = 5
    started_at = time.monotonic()
    while True:
        try:
            dir_one.rename(dir_two)
        except FileNotFoundError:
            _logger.info("Wait until %s becomes available", dir_one)
        if time.monotonic() - started_at > timeout_sec:
            break
        time.sleep(1)


_logger = logging.getLogger(__name__)
