# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from directories.prerequisites._warehouse import PrerequisiteStore

_logger = logging.getLogger(__name__)


class LocalStore(PrerequisiteStore, metaclass=ABCMeta):

    def __init__(self, local_dir: Path):
        if local_dir.drive and not local_dir.is_absolute():
            raise ValueError(
                "Relative paths within a specific disk are intentionally "
                "prohibited, because it's a common source of bugs."
                "Don't strip the trailing / from a Windows disk root. "
                "It matters because on Windows paths consists of a disk and "
                "a path within the disk. These components  are independent "
                "of each other. I.e. C: is the current directory of the disk "
                "and C:\\ is the root of the disk. Appending a relative path "
                "foo/bar gives C:foo\\bar and C:\\foo\\bar respectively. "
                "See: https://docs.microsoft.com/en-us/dotnet/standard/io/file-path-formats")
        self._local_dir = local_dir

    def __repr__(self):
        return f"{self.__class__.__name__}({self._local_dir})"

    def fetch(self, relative_path: str) -> Path:
        target_file = self._local_dir / relative_path
        if not target_file.exists():
            raise RuntimeError(
                f"File {target_file} does not exist, "
                "check prerequisite URL or source dir structure")
        return target_file

    def url(self, relative_path: str) -> str:
        raise ValueError("Cannot get URL from local prerequisite store")

    def hostname(self) -> str:
        raise ValueError("Cannot get hostname of local prerequisite store")


class FileUrlStore(LocalStore):

    def __init__(self, url: str):
        self._url = url
        parsed = urlparse(url)
        if parsed.scheme != 'file':
            raise ValueError(f"Only file:// URLs are supported: {url}")
        if parsed.netloc:
            raise ValueError(f"Only local file:// URLs are supported: {url}")
        super().__init__(Path(url2pathname('//' + parsed.path)))

    def __repr__(self):
        return f"{self.__class__.__name__}({self._url})"
