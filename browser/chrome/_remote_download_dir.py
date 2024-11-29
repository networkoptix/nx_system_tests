# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Collection

from browser.chrome import ChromeConfiguration
from os_access import RemotePath


class RemoteChromeDownloadDirectory:

    def __init__(self, path: RemotePath):
        self._path = path

    def apply_to(self, configuration: ChromeConfiguration):
        # See: https://android.googlesource.com/platform/external/chromium/+/ics-aah-release/chrome/common/pref_names.cc
        configuration.set_preference('download.default_directory', str(self._path))

    def list_finished(self) -> Collection[RemotePath]:
        result = []
        for file in self._path.iterdir():
            if file.name.startswith(".com.google.Chrome"):
                _logger.debug("Skip google cache file %s", file)
            elif file.suffix == '.crdownload':
                _logger.debug("Skip download temporary file %s", file)
            else:
                result.append(file)
        return result


_logger = logging.getLogger(__name__)
