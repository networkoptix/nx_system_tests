# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

_logger = logging.getLogger(__name__)


class _CIInfo:

    def __init__(self, ci_info_raw: bytes):
        try:
            ci_info_decoded = ci_info_raw.decode('ascii', errors='backslashreplace')
        except UnicodeDecodeError as e:
            raise RuntimeError(f"Cannot decode ci_info.txt content: {e}")
        ci_info = {}
        for line in ci_info_decoded.splitlines():
            [key, sep, value] = line.partition('=')
            if not sep:
                _logger.debug("Invalid line in ci_info.txt: %r", line)
                ci_info[key] = None
            else:
                ci_info[key] = value
        self._ci_info = ci_info

    def __repr__(self):
        return f'<{self.__class__.__name__}> {self._ci_info}'

    def updates_url(self) -> str:
        url = self._ci_info.get('UPDATES_URL')
        if url is None:
            raise RuntimeError("There is no field UPDATES_URL in ci_info.txt")
        if not url:
            raise _UpdatesUrlEmpty("UPDATES_URL in ci_info.txt is empty")
        return url


class _UpdatesUrlEmpty(Exception):
    pass
