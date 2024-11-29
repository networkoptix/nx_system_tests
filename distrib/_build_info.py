# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import logging
import re
from abc import ABCMeta
from abc import abstractmethod
from typing import Mapping
from typing import Optional
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen

from distrib._customizations import Customization
from distrib._customizations import known_customizations
from distrib._version import Version

_logger = logging.getLogger(__name__)


class BuildInfo(metaclass=ABCMeta):

    @abstractmethod
    def as_dict(self) -> Mapping[str, Optional[str]]:
        pass

    @abstractmethod
    def branch(self) -> str:
        pass

    @abstractmethod
    def version(self) -> Version:
        pass

    @abstractmethod
    def customization(self) -> Customization:
        pass

    @abstractmethod
    def cloud_host(self) -> str:
        pass

    @abstractmethod
    def short_sha(self) -> str:
        pass


class RawBytesBuildInfo(BuildInfo):

    def __init__(self, build_info_raw: bytes):
        try:
            build_info_decoded = build_info_raw.decode('ascii', errors='backslashreplace')
        except UnicodeDecodeError as e:
            raise BuildInfoError(e)
        build_info = {}
        for line in build_info_decoded.splitlines():
            [key, sep, value] = line.partition('=')
            if not sep:
                _logger.debug("Invalid line in build_info.txt: %r", line)
                build_info[key] = None
            else:
                build_info[key] = value
        self._build_info = build_info
        self._raw = build_info_raw

    def __repr__(self):
        words = []
        merge_request_id = self._merge_request_id()
        if merge_request_id is not None:
            words.append(f'!{merge_request_id}')
        else:
            if 'version' in self._build_info:
                words.append(self._build_info['version'])
            if 'changeSet' in self._build_info:
                words.append(self._build_info['changeSet'])
        if 'branch' in self._build_info:
            words.append(self._build_info['branch'])
        if 'customization' in self._build_info:
            if self._build_info['customization'] != 'default':
                words.append(self._build_info['customization'])
        if not words:
            words.append('empty')
        words = ' '.join(words)
        return f'<{self.__class__.__name__} {words}>'

    def short_sha(self) -> str:
        return self._build_info.get('changeSet')

    def _merge_request_id(self) -> Optional[int]:
        match = re.search(
            r"merge-requests/(?P<merge_request_id>\d+)", self._build_info['currentRefs'])
        if match is None:
            return None
        return int(match.group('merge_request_id'))

    def version(self) -> Version:
        if 'version' in self._build_info:
            return Version(self._build_info['version'])
        return None

    def customization(self) -> Customization:
        return known_customizations[self._build_info['customization']]

    def cloud_host(self) -> str:
        return self._build_info['cloudHost']

    def branch(self) -> str:
        return self._build_info.get('branch')

    def as_dict(self) -> Mapping[str, Optional[str]]:
        return {**self._build_info}


class PathBuildInfo(RawBytesBuildInfo):

    def __init__(self, path):
        self._path = path
        if self._path.name != 'build_info.txt':
            raise BuildInfoError("Build info file must be build_info.txt")
        super().__init__(self._path.read_bytes())

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._path}>"


class DistribUrlBuildInfo(RawBytesBuildInfo):

    def __init__(self, url: str):
        self._url = url
        if not url.endswith('/'):  # Respect multiple trailing slashes
            url += '/'
        text_url = url + 'build_info.txt'
        try:
            _logger.info("Request: %s", text_url)
            with urlopen(Request(text_url)) as response:
                contents = response.read()
        except HTTPError as e:
            if e.code == 404:
                _logger.debug("Not Found: %s: %r", text_url, e)
                raise BuildInfoNotFound(f"{text_url} is not found")
            else:
                _logger.warning("Request failed: %s: %r", text_url, e)
                raise BuildInfoError(f"Failed to get {self._url}: {e}")
        except (URLError, TimeoutError) as e:
            _logger.warning("Request failed: %s: %r", text_url, e)
            raise BuildInfoError(f"Failed to get {self._url}: {e}")
        super().__init__(contents)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._url!r})"


class BuildInfoError(Exception):
    pass


class BuildInfoNotFound(BuildInfoError):
    pass
