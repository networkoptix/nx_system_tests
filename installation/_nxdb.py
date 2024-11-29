# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections.abc import Collection
from pathlib import PurePath

from installation._video_archive import ArchiveDirectory


class Nxdb:

    def __init__(
            self,
            video_archive_files: ArchiveDirectory,
            server_guid: str,
            ):
        self._video_archive_files = video_archive_files
        self._server_guid = server_guid

    def exists(self) -> bool:
        # After VMS-42087 nxdb files location changed.
        # rglob must be replaces by glob when older version obsolete.
        return len(self._video_archive_files.search_file_recursively('.', f'{self._server_guid}*.nxdb')) > 0

    def remove(self):
        # After VMS-42087 nxdb files location changed.
        # rglob must be replaces by glob when older version obsolete.
        rel_results = self._video_archive_files.search_file_recursively('.', f'{self._server_guid}*.nxdb')
        for nxdb_file in rel_results:
            self._video_archive_files.unlink_file(nxdb_file)

    def list_files(self) -> Collection[PurePath]:
        return self._video_archive_files.search_file_recursively('.', f'{self._server_guid}*.nxdb')
