# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Mapping

from installation._mediaserver import Mediaserver
from installation._mediaserver import ServerGuidNotFound
from installation._os_metrics import OsCollectingMetrics


class MediaserverMetrics:

    def __init__(self, mediaserver: Mediaserver):
        self._mediaserver = mediaserver
        self._os_metrics = OsCollectingMetrics(self._mediaserver.os_access)

    def get_os_metrics(self) -> Mapping:
        os_access = self._mediaserver.os_access
        process_metrics = {}
        vms_pid = self._mediaserver.service.status().pid
        if vms_pid != 0:
            memory_usage = os_access.get_ram_usage(vms_pid)
            process_metrics = {
                'vms_memory_usage_peak_bytes': memory_usage.process_usage_peak_bytes,
                'vms_memory_usage_bytes': memory_usage.process_usage_bytes,
                'vms_memory_usage': memory_usage.process_usage,
                'vms_cpu_usage_seconds': os_access.get_cpu_time_process(vms_pid),
                }
            try:
                process_metrics['vms_open_files_count'] = os_access.get_open_files_count(vms_pid)
            except OSError:
                _logger.exception('Cannot count open files')
        db_size_metrics = {
            'analytics_db': self._mediaserver.analytics_database_size(),
            'video_archive': self._mediaserver.video_archive_size(),
            }
        db_files = [
            self._mediaserver.ecs_db,
            self._mediaserver.mserver_db,
            ]
        try:
            server_guid = self._mediaserver.get_mediaserver_guid()
        except ServerGuidNotFound:
            server_guid = None
        object_detection_dbs = self._mediaserver.list_object_detection_db()
        if server_guid in object_detection_dbs:
            db_files.append(object_detection_dbs[server_guid])
        for file in db_files:
            try:
                db_size_metrics[file.name] = file.size()
            except FileNotFoundError:
                _logger.info("%s is not found", file)
        return {
            **self._os_metrics.get_current(),
            **db_size_metrics,
            **process_metrics,
            }


_logger = logging.getLogger(__name__)
