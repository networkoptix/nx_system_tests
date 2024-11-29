# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""Store URLs in snapshot names.

>>> url = 'https://artifactory.ru.nxteam.dev/artifactory/build-vms-nightly/master/3889/default/distrib/'
>>> assert len(compress_url(url)) <= 30
>>> assert decompress_url(compress_url(url)) == url
>>> decompress_url('irrelevant')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError: ...
>>> decompress_url('9irrelevant')  # doctest: +ELLIPSIS
Traceback (most recent call last):
    ...
RuntimeError: ...
"""
import logging
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode
from functools import lru_cache
from pathlib import Path
from zlib import compressobj
from zlib import decompressobj


def compress_url(url: str) -> str:
    url_bytes = url.encode(_url_encoding)
    packer = _get_packer()
    url_compressed = packer.compress(url_bytes) + packer.flush()
    url_compressed_encoded = urlsafe_b64encode(url_compressed).decode(_url_encoding)
    version_str = f"{_zdict_archive_version:0{_zdict_version_length}}"
    result = version_str + url_compressed_encoded
    logging.debug("Compress URL %s to %s", url, result)
    return result


def decompress_url(value: str) -> str:
    version_str = value[:_zdict_version_length]
    if not version_str.isdigit():
        raise RuntimeError(
            f"{version_str} contains non-digit characters while only "
            f"{_zdict_version_length} digits are allowed")
    unpacker = _get_unpacker(int(version_str))
    url_compressed_encoded = value[_zdict_version_length:]
    url_compressed = urlsafe_b64decode(url_compressed_encoded)
    url_bytes = unpacker.decompress(url_compressed) + unpacker.flush()
    return url_bytes.decode(_url_encoding)


@lru_cache()
def _zdict(version: int) -> bytes:
    path = Path(__file__).with_name(f'zdict_{version}.urls')
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise RuntimeError(f"Can't find a ZLIB dictionary {path}")


def _get_packer():
    zdict = _zdict(_zdict_archive_version)
    return compressobj(zdict=zdict)


def _get_unpacker(version: int):
    zdict = _zdict(version)
    return decompressobj(zdict=zdict)


_zdict_archive_version = 0
_zdict_version_length = 1  # seems 0..9 is more that enough for versioning
_url_encoding = 'ascii'
