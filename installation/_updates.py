# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import time
import wsgiref.simple_server
import zipfile
from contextlib import contextmanager
from pathlib import Path
from pathlib import PurePosixPath
from threading import Thread
from typing import Collection
from typing import Optional
from typing import Sequence

from directories.prerequisites import PrerequisiteStore
from distrib import InstallerName
from distrib import InstallerSet
from distrib import Version

_logger = logging.getLogger(__name__)


class UpdateServer:

    def __init__(self, archive: LocalUpdateArchive, hostname: str, bytes_per_sec=10 * 1024**2):
        self._archive: LocalUpdateArchive = archive
        self._bytes_per_sec = bytes_per_sec
        self._hostname = hostname
        self._port = 0
        self._token_bucket = _TokenBucket(capacity=bytes_per_sec, tokens_per_sec=bytes_per_sec)
        self._server = None
        self._thread = None

    @contextmanager
    def serving(self):
        server = wsgiref.simple_server.make_server('0.0.0.0', self._port, self._app)
        [_, self._port] = server.server_address
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def update_info(self):
        return self._archive.make_update_info(self._url())

    def _url(self) -> str:
        if self._port == 0:
            raise RuntimeError(
                "Server's port is 0, i.e. dynamic; "
                "it's realized will be known when server start serving")
        return f'http://{self._hostname}:{self._port}/'

    def _app(self, environ, start_response):
        try:
            path_info = environ['PATH_INFO']
            package_name = PurePosixPath(path_info).name
            file_size = self._archive.package_size(package_name)
            [content_type, _] = mimetypes.guess_type(path_info)
            http_range = environ.get('HTTP_RANGE', None)
            if http_range:
                # Range header contains value like "bytes=0-1023" (multiple ranges are not supported).
                [_, bytes_range] = http_range.split('=')
                [range_from, range_to] = [int(value) for value in bytes_range.split('-')]
                range_to = min(range_to, file_size)
                if range_to == file_size:
                    # Last byte of the file will not be read.
                    content_length = range_to - range_from
                else:
                    content_length = range_to - range_from + 1
                start_response('206 Partial Content', [
                    ('Content-Length', f'{content_length}'),
                    ('Content-Range', f'bytes {range_from}-{range_to}/{file_size}'),
                    ('Content-Type', content_type),
                    ])
                yield from self._read_data(package_name, range_from, range_to)
                _logger.info(
                    "%r: Request %s, range %s: Complete",
                    self, path_info, http_range)
            else:
                start_response('200 OK', [
                    ('Content-Length', f'{file_size}'),
                    ('Content-Type', content_type),
                    ])
                yield from self._read_data(package_name, 0, file_size)
                _logger.info(
                    "%r: Request %s: Complete",
                    self, path_info, http_range)
        except Exception:
            request = dict(environ.items() - os.environ.items())
            _logger.exception("%r: Request %r: Exception", self, request)
            raise

    def _read_data(self, package_name, start_pos, end_pos):
        file_path = self._archive.package_path(package_name)
        chunk_size_bytes = self._bytes_per_sec or 1024**2
        with open(file_path, 'rb') as fp:
            current_pos = start_pos
            fp.seek(current_pos)
            while True:
                next_chunk_size = min(end_pos - current_pos + 1, chunk_size_bytes)
                if next_chunk_size == 0:
                    break
                data = fp.read(next_chunk_size)
                current_pos += next_chunk_size
                self._token_bucket.wait_for_filling(next_chunk_size)
                yield data


class LocalUpdateArchive:

    def __init__(
            self,
            installer_set: InstallerSet,
            warehouse: PrerequisiteStore,
            platforms: Optional[Collection[str]] = None,
            ):
        update_names = installer_set.update_names()
        packages = []
        for name in update_names:
            if platforms is not None and name.platform not in platforms:
                _logger.info(f"Skipping unused platform: {name}")
                continue
            packages.append(UpdateInstaller(name, warehouse))
        if not packages:
            raise RuntimeError(f"No server updates: {installer_set!r}")
        self._packages: Sequence[UpdateInstaller] = packages

    def version(self) -> Version:
        return self._packages[0].name.version

    def make_update_info(self, updates_server_url: str):
        [installer, *_] = self._packages
        [version] = {i.name.version for i in self._packages}
        info = {
            'version': str(version),
            'cloud_host': installer.extract_cloud_host(),
            'packages': [
                installer.update_package_info(updates_server_url)
                for installer in self._packages
                ],
            }
        return info

    def package_size(self, name: str) -> int:
        for installer in self._packages:
            if installer.path.name == name:
                break
        else:
            raise RuntimeError(f"Update file {name!r} not found")
        return installer.size

    def package_path(self, name: str) -> Path:
        for installer in self._packages:
            if installer.path.name == name:
                break
        else:
            raise RuntimeError(f"Update file {name!r} not found")
        return installer.path


class UpdateInstaller:

    def __init__(self, name: InstallerName, warehouse: PrerequisiteStore):
        installer_path = warehouse.fetch(name.full_name)
        md5_checksum = _md5_checksum(installer_path)
        try:
            signature_path = warehouse.fetch(name.full_name + '.sig')
        except FileNotFoundError:
            signature = ''
        else:
            signature = signature_path.read_text(encoding='ascii')
        size = installer_path.stat().st_size
        self.name = name
        self.full_name = self.name.full_name
        self.path = installer_path
        self._md5_checksum = md5_checksum
        self._signature = signature
        self.size = size

    def extract_cloud_host(self) -> str:
        with zipfile.ZipFile(self.path) as installer_zip:
            update_zip_info = installer_zip.getinfo('package.json')
            with installer_zip.open(update_zip_info.filename) as update_info_file:
                update_info = json.loads(update_info_file.read())
                return update_info['cloudHost']

    def update_package_info(self, updates_server_url: str):
        package_name = self.full_name
        return {
            'platform': self.name.platform,
            'file': 'updates/{}/{}'.format(self.name.version.build, package_name),
            'url': updates_server_url + package_name,
            'size': self.size,
            'md5': self._md5_checksum,
            'signature': self._signature,
            }


class _TokenBucket:

    def __init__(self, capacity, tokens_per_sec):
        self._capacity = capacity
        self._tokens_per_sec = tokens_per_sec
        self._tokens = capacity
        self._timestamp = time.monotonic()

    def wait_for_filling(self, tokens):
        if tokens > self._capacity:
            raise RuntimeError(
                f"Cannot get {tokens} tokens from the bucket with {self._capacity} capacity.")

        if self._tokens < self._capacity:
            now = time.monotonic()
            delta = self._tokens_per_sec * (now - self._timestamp)
            self._tokens = min(self._capacity, self._tokens + delta)
            self._timestamp = now

        if tokens > self._tokens:
            deficit = tokens - self._tokens
            delay = deficit / self._tokens_per_sec
            time.sleep(delay)

        self._tokens -= tokens


def _md5_checksum(local_path: Path) -> str:
    cache = local_path.with_suffix(local_path.suffix + '.md5')
    if not local_path.exists():
        cache.unlink(missing_ok=True)
        raise RuntimeError(f"Cannot compute MD5 checksum for {local_path}: file not exists")
    try:
        return cache.read_text()
    except FileNotFoundError:
        pass
    _logger.info("Compute MD5 checksum for the file %s", local_path)
    hash_object = hashlib.md5()
    with local_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hash_object.update(chunk)
    cache.write_text(hash_object.hexdigest())
    return hash_object.hexdigest()
