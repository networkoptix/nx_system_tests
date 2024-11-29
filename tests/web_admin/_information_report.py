# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.chrome import RemoteChromeDownloadDirectory


def get_single_report_data(
        downloads_directory: RemoteChromeDownloadDirectory, timeout: float) -> bytes:
    timeout_at = time.monotonic() + timeout
    while True:
        try:
            [single_file] = downloads_directory.list_finished()
        except ValueError as err:
            if 'not enough values to unpack' not in str(err):
                raise
            if time.monotonic() > timeout_at:
                raise
            time.sleep(0.1)
            continue
        return single_file.read_bytes()
