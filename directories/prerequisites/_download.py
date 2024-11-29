# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import logging
import os
import re
import subprocess
import time
from http import HTTPStatus
from pathlib import Path
from pathlib import PurePosixPath
from typing import Optional
from typing import Sequence
from urllib.error import HTTPError
from urllib.parse import unquote
from urllib.parse import urlparse
from urllib.request import urlopen

from directories.filelocker import wait_locked_exclusively


def concurrent_safe_download(source_url: str, destination_dir: Path) -> Path:
    if not destination_dir.is_dir():
        raise RuntimeError(f"Should be a directory: {destination_dir=}")
    destination = destination_dir / _get_resource_name(source_url)
    lock_file = destination.with_name(destination.name + ".lock")
    with wait_locked_exclusively(lock_file, _http_download_timeout + 5):
        if not destination.exists():
            _download(source_url, destination)
    return destination


def _download(source_url: str, destination: Path):
    _logger.info("Download: start: %s -> %s", source_url, destination)
    scheme = urlparse(source_url).scheme
    if scheme in ('http', 'https'):
        _http_download(source_url, destination)
    elif scheme == 'file':
        _move_file(source_url, destination)
    else:
        raise RuntimeError(f'Unsupported URL scheme: {scheme}')


def _http_download(source_url: str, destination: Path):
    tmp_file = destination.with_suffix('.download')
    process = CurlProcess(
        args=[
            '--output', str(tmp_file),
            '--continue-at', '-',
            '--fail',
            '--location',
            '--connect-timeout', '10',
            ],
        url=source_url)
    process.wait()
    expected_md5_hash = _get_source_md5(source_url)
    if expected_md5_hash is not None:
        actual_md5_hash = hashlib.md5()
        with tmp_file.open('rb') as f:
            while chunk := f.read(1024 * 1024):
                actual_md5_hash.update(chunk)
        if expected_md5_hash != actual_md5_hash.hexdigest():
            tmp_file.unlink()
            raise RuntimeError(
                f"Checksum for {destination} mismatch. "
                f"Server checksum: {expected_md5_hash}. "
                f"Local checksum {actual_md5_hash}")
    tmp_file.replace(destination)


class CurlProcess:

    def __init__(self, args: Sequence[str], url: str):
        self._process = subprocess.Popen(['curl', *args, url], stderr=subprocess.PIPE)
        self._url = url
        self._started_at = time.monotonic()
        self._buffer = bytearray()

    def wait(self):
        _logger.info("Running command %r pid=%d" % (self._process.args, self._process.pid))
        interval = 0.1
        last_line = None
        while True:
            try:
                exit_code = self._process.wait(interval)
            except subprocess.TimeoutExpired:
                exit_code = None
            lines = self._list_lines()
            last_line = lines[-1] if lines else last_line
            for line in lines:
                _logger.info(line)
            if exit_code is not None:
                if exit_code == 0:
                    break
                if last_line is None:
                    raise RuntimeError(f"{self._process.args} produced no output before exit with {exit_code=}")
                if exit_code == 22:
                    [_, error_code] = last_line.rsplit('error: ', maxsplit=1)
                    raise DownloadHTTPError(self._url, int(error_code))
                else:
                    raise RuntimeError(f"curl {self._process.args} finished with {exit_code=}: {last_line!r}")
            if time.monotonic() - self._started_at > _http_download_timeout:
                raise TimeoutError(f"Timed out downloading file: {self._process.args}")
            interval = min(interval * 1.5, 10)
        _logger.info("Finished command %r pid=%d" % (self._process.args, self._process.pid))

    def _list_lines(self):
        self._buffer.extend(self._process.stderr.read1())
        return _read_console_lines(self._buffer)


def _read_console_lines(buffer: bytearray):
    r"""Parse console lines and \r-like status updates.

    >>> import os
    >>> sep = os.linesep
    >>> buffer = f'first{sep}status1\rstatus2\rstatus3{sep}second'
    >>> _read_console_lines(bytearray(buffer.encode()))
    ['first', 'status3']
    >>> buffer = f'first{sep}status1\rstatus2\rstatu'
    >>> _read_console_lines(bytearray(buffer.encode()))
    ['first', 'status2']
    >>> buffer = f'first{sep}status1\rstatus2{sep}second{sep}thir'
    >>> mutable_array = bytearray(buffer.encode())
    >>> _read_console_lines(mutable_array)
    ['first', 'status2', 'second']
    >>> mutable_array
    bytearray(b'thir')
    """
    [*whole_lines, last_line] = buffer.split(os.linesep.encode())
    result = [line.rsplit(b'\r', 1)[-1] for line in whole_lines]
    [partial_line, _sep, rest] = last_line.rpartition(b'\r')
    if partial_line:
        result.append(partial_line.rsplit(b'\r', 1)[-1])
    buffer[:] = rest
    return [line.decode('utf8') for line in result]


def _move_file(source_url: str, destination: Path):
    path = Path(re.sub(r'^/([A-Z]\:)/', r'\1/', unquote(urlparse(source_url).path)))
    if not path.exists():
        raise RuntimeError(f"File {source_url} does not exist or is not a local file")
    path.replace(destination)
    md5_path = path.with_name(path.name + '.md5')
    if md5_path.exists():
        md5_path.replace(destination.with_name(destination.name + '.md5'))


def _get_source_md5(source_url: str) -> Optional[str]:
    try:
        response = urlopen(source_url + '.md5', timeout=10)
    except HTTPError as e:
        if e.code == HTTPStatus.NOT_FOUND:
            return None
        raise
    content = response.read()
    md5_line = content.decode('utf-8').strip()
    try:
        [md5_hash, md5_filename] = md5_line.split()
    except ValueError:
        _logger.info("MD5 is not in expected format <hash> <filename>: %s", md5_line)
        return None
    resource_name = _get_resource_name(source_url)
    if resource_name != md5_filename:
        raise RuntimeError(
            "Received MD5 hash for a wrong file; "
            f"expected {resource_name}, got {md5_filename}")
    return md5_hash


def _get_resource_name(url: str) -> str:
    """Parse resource name from URL.

    >>> _get_resource_name('http://example.com/path/to/file.old.txt')
    'file.old.txt'
    >>> _get_resource_name('http://example.com/path/to/file%3D%3D.txt')
    'file==.txt'
    >>> _get_resource_name('http://example.com/path/to/folder')
    'folder'
    >>> _get_resource_name('http://example.com/path/to/folder/')
    'folder'
    """
    return PurePosixPath(unquote(urlparse(url).path)).name


class DownloadHTTPError(Exception):

    def __init__(self, url, error_code: int):
        super().__init__(f"<DownloadHTTPError {error_code}: {HTTPStatus(error_code).phrase} on {url!r}>")
        self.code = error_code


_logger = logging.getLogger(__name__)
_http_download_timeout = 120 * 60
