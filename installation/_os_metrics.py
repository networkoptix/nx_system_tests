# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import Any
from typing import Mapping
from typing import Optional

from os_access import DiskIoInfo
from os_access import OsAccess


class OsCollectingMetrics:

    def __init__(self, os_access: OsAccess):
        self._os_access = os_access
        self._io_base = {io_time.name: io_time for io_time in self._os_access.get_io_time()}
        self._latest_io = dict(self._io_base)
        self._latest_timestamp = time.monotonic()

    def get_current(self) -> Mapping[str, Any]:
        result = {}
        duration = time.monotonic() - self._latest_timestamp
        result['drive'] = []
        io_current_all = self._os_access.get_io_time()
        for io_current in io_current_all:
            io_base = self._io_base.get(io_current.name)
            slice_io = self._get_slice_io(io_current, io_base)
            slice_io_latest = self._get_slice_io(io_current, self._latest_io.get(io_current.name))
            io_metrics: dict[str, float] = {
                'name': io_current.name,
                'reading_sec': slice_io.reading_sec,
                'writing_sec': slice_io.writing_sec,
                'read_bytes': slice_io.read_bytes,
                'write_bytes': slice_io.write_bytes,
                'read_count': slice_io.read_count,
                'write_count': slice_io.write_count,
                'iops_read': slice_io_latest.read_count / duration,
                'iops_write': slice_io_latest.write_count / duration,
                'iops_bytes_read': slice_io_latest.read_bytes / duration,
                'iops_bytes_write': slice_io_latest.write_bytes / duration,
                }
            result['drive'].append(io_metrics)
        result['drive'].sort(key=lambda x: x['iops_read'] + x['iops_write'], reverse=True)
        result['disk'] = result['drive'][0]
        result['cpu_usage'] = self._os_access.get_cpu_usage()
        self._latest_io = {io_time.name: io_time for io_time in io_current_all}
        self._latest_timestamp = time.monotonic()
        return result

    @staticmethod
    def _get_slice_io(current: DiskIoInfo, prev: Optional[DiskIoInfo]) -> DiskIoInfo:
        previous = DiskIoInfo('', 0, 0, 0, 0, 0, 0) if prev is None else prev
        return DiskIoInfo(
            name=current.name,
            reading_sec=current.reading_sec - previous.reading_sec,
            writing_sec=current.writing_sec - previous.writing_sec,
            read_bytes=current.read_bytes - previous.read_bytes,
            write_bytes=current.write_bytes - previous.write_bytes,
            read_count=current.read_count - previous.read_count,
            write_count=current.write_count - previous.write_count,
            )
