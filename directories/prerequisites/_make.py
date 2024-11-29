# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from directories import get_ft_artifacts_root
from directories.prerequisites._http import _HttpStore
from directories.prerequisites._local import FileUrlStore
from directories.prerequisites._warehouse import PrerequisiteStore

_logger = logging.getLogger(__name__)

_nx_cache_dir = get_ft_artifacts_root() / 'prerequisites-cache'


def make_prerequisite_store(url: str, cache_dir: Path = _nx_cache_dir) -> PrerequisiteStore:
    if url.startswith(('http://', 'https://')):
        return _HttpStore(url, cache_dir)
    elif url.startswith('file:///'):
        return FileUrlStore(url)
    raise RuntimeError(f"Unknown URL format {url}. URL must be a HTTP(S) URL or a local file URI")
