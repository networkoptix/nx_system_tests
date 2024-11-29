# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from urllib.parse import urlparse

from directories.prerequisites import DownloadHTTPError
from directories.prerequisites._download import concurrent_safe_download
from directories.prerequisites._warehouse import PrerequisiteStore

_logger = logging.getLogger(__name__)


class _HttpStore(PrerequisiteStore):

    def __init__(self, url: str, cache_dir: Path):
        self._local_dir = cache_dir
        self._url = url.rstrip('/')

    def __repr__(self):
        return f"{self.__class__.__name__}({self._url})"

    def fetch(self, relative_path):
        target_file = self._local_dir / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        url = self.url(relative_path)
        _logger.info("Fetch prerequisite from %s to %s", url, target_file.parent)
        try:
            return concurrent_safe_download(url, target_file.parent)
        except DownloadHTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(url)
            raise

    def url(self, relative_path: str) -> str:
        return f'{self._url}/{relative_path}'

    def hostname(self) -> str:
        return urlparse(self._url).hostname
