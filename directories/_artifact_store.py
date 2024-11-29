# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import logging
import os
import socket
from pathlib import Path
from typing import Mapping
from typing import Set
from urllib.parse import unquote

from config import global_config


def make_artifact_store():
    if 'http_share' in global_config:
        root, url = global_config['http_share'].split(os.pathsep, 1)
        root = root.format(
            home=Path.home(),
            username=getpass.getuser(),
            hostname=socket.gethostname(),
            )
        url = url.format(
            home=Path.home(),
            username=getpass.getuser(),
            hostname=socket.gethostname(),
            )
        _logger.debug("Artifacts will published at %s", url)
        root = Path(root)
        return _ArtifactStore({root: url})
    else:
        _logger.debug("Artifacts will be accessible locally")
        return _ArtifactStore({})


class _ArtifactStore:

    def __init__(self, shares: Mapping[Path, str]):
        self._shares = shares
        self._already_published: Set[Path] = set()

    def store_one(self, path: Path):
        return self._make_url(path)

    def get_local_path(self, uri: str) -> Path:
        for share, share_url in self._shares.items():
            if uri.startswith(share_url):
                relative_path = unquote(uri.replace(share_url, '').lstrip('/'))
                return Path(share, relative_path)
        raise NotALocalArtifact(uri)

    def _make_url(self, path):
        # Making a URL from a path is more sophisticated that it seems.
        # See how as_uri() differ on Windows and POSIX.
        # Implementation uses as few assumptions as possible.
        path_url = path.as_uri()
        for share, share_url in self._shares.items():
            if path == share:
                return share_url
            for parent in path.parents:
                if parent != share:
                    continue
                # Share and parent may be equivalent as path but generate
                # different URLs because of, for example, the letter case.
                parent_url = parent.as_uri()
                assert path_url.startswith(parent_url)
                relative = path_url[len(parent_url):]
                if share_url.endswith('/'):
                    # Preserve slashes in the share URL, strip the other part.
                    url = share_url + relative.lstrip('/')
                else:
                    url = share_url + relative
                _logger.info("Store artifact as a shared URL: %s", url)
                return url
        _logger.info("Store artifact as a local file: %s", path_url)
        return path_url

    def store_new(self, directory, nested=True):
        urls = []
        if nested:
            paths = directory.rglob('*')
        else:
            paths = directory.glob('*')
        for path in paths:
            if path.is_dir():
                continue
            if path in self._already_published:
                continue
            url = self.store_one(path)
            urls.append(url)
            self._already_published.add(path)
        return urls


class NotALocalArtifact(Exception):
    pass


_logger = logging.getLogger(__name__)
