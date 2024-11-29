# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import io
import tempfile
import time
import zipfile
from collections.abc import ByteString
from collections.abc import Iterable
from collections.abc import Mapping
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Optional
from uuid import UUID

from mediaserver_api._mediaserver import _format_uuid
from mediaserver_api._mediaserver_v1 import MediaserverApiV1


class LogType(Enum):
    MAIN = 'mainLog'
    HTTP = 'httpLog'
    SYSTEM = 'systemLog'


class MediaserverApiV2(MediaserverApiV1):

    _version = 'v2'

    def _get_camera_thumbnail(
            self,
            camera_id,
            height: Optional[int] = None,
            when: Optional[datetime] = None,
            ) -> ByteString:
        params = {}
        if height is not None:
            params['size'] = f'{height}x{height}'
        if when is not None:
            time_formatted = when.isoformat(sep='T', timespec='milliseconds')
            params['timestampUs'] = time_formatted
            params['roundMethod'] = 'precise'  # It may be a bit costly though
        return self._http_download(
            f'rest/{self._version}/devices/{_format_uuid(camera_id)}/image', params)

    def list_hwids(self):
        response = self.http_get(f'rest/{self._version}/servers/this/runtimeInfo')
        return response['runtimeData']['hardwareIds']

    def _get_raw_metric_values(self):
        return self.http_get(f'rest/{self._version}/{self._site_term}/metrics/values')

    def get_filtered_raw_metric_values(self, *metric_path: str | UUID):
        # Note that the metric_path must match the path from the server response, for example:
        # [systems, *, info] and not [system_info].
        if metric_path:
            filters = '.'.join([str(path) for path in metric_path])
            return self.http_get(f'rest/{self._version}/{self._site_term}/metrics/values?_with={filters}')
        return self.http_get(f'rest/{self._version}/{self._site_term}/metrics/values')

    def _get_raw_metric_alarms(self):
        return self.http_get(f'rest/{self._version}/{self._site_term}/metrics/alarms')

    def get_server_uptime_sec(self) -> float:
        metric_values = self.http_get(
            f'rest/{self._version}/{self._site_term}/metrics/values?_with=servers&_local=true')
        servers_info = metric_values['servers'].values()
        [server_info] = servers_info
        return server_info['availability']['uptimeS']

    def _start_manual_cameras_search(self, camera_url, credentials):
        data = {'target': {'ip': camera_url}}
        if credentials:
            data['credentials'] = credentials
        response = self.http_post(f'rest/{self._version}/devices/*/searches', data)
        return self._get_search_id(response)

    @staticmethod
    def _get_search_id(raw_data) -> UUID:
        return UUID(raw_data['id'])

    def add_dummy_smb_storage(self, index, parent_id=None):
        raise NotImplementedError("Unable to add storage using fake data in APIv2")

    def rebuild_main_archive(self):
        self._rebuild_archive(main_pool='main')

    def rebuild_backup_archive(self):
        self._rebuild_archive(main_pool='backup')

    def _start_rebuild_archive(self, main_pool: str):
        self.http_post(f'rest/{self._version}/servers/this/rebuildArchive/{main_pool}', {})

    def _rebuild_archive_in_progress(self, main_pool: str) -> bool:
        response = self.http_get(
            f'rest/{self._version}/servers/this/rebuildArchive/{main_pool}',
            self._keep_default_params)
        storage_status = response[main_pool]
        known_states = ('none', 'full', 'partial')
        if storage_status['state'] not in known_states:
            raise RuntimeError(f"Unknown rebuild archive state: {storage_status['state']}")
        return storage_status['state'] != 'none'

    def list_log_levels(self) -> Mapping[LogType, Optional[str]]:
        settings = self.http_get(f'rest/{self._version}/servers/this/logSettings')
        return {log: settings[log.value].get('primaryLevel', None) for log in LogType}

    def set_log_levels(self, log_levels: Mapping[LogType, str]):
        level_settings = {log.value: {'primaryLevel': level} for log, level in log_levels.items()}
        self.http_patch(f'rest/{self._version}/servers/this/logSettings', level_settings)

    def set_system_log_levels(self, log_levels: Mapping[LogType, str]):
        level_settings = {log.value: {'primaryLevel': level} for log, level in log_levels.items()}
        self.http_patch(f'rest/{self._version}/servers/*/logSettings', level_settings)

    def set_max_log_file_size(self, limit_bytes: int):
        self.http_patch(f'rest/{self._version}/servers/this/logSettings', {
            'maxFileSizeB': limit_bytes,
            })

    def set_max_log_volume_size(self, limit_bytes: int):
        self.http_patch(f'rest/{self._version}/servers/this/logSettings', {
            'maxVolumeSizeB': limit_bytes,
            })

    def set_max_log_file_time_duration(self, duration_sec: int):
        self.http_patch(f'rest/{self._version}/servers/this/logSettings', {
            'maxFileTimePeriodS': duration_sec,
            })

    @contextmanager
    def all_logs_extracted(self) -> AbstractContextManager[Iterable[Path]]:
        archive = self._http_download(f'rest/{self._version}/servers/this/logArchive')
        with self._logs_extracted(archive) as logs:
            yield logs

    @staticmethod
    @contextmanager
    def _logs_extracted(archive: bytes) -> AbstractContextManager[Iterable[Path]]:
        with tempfile.TemporaryDirectory() as td:
            with zipfile.ZipFile(io.BytesIO(archive), 'r') as zfp:
                zfp.extractall(td)
            temp_dir = Path(td)
            yield temp_dir.iterdir()

    @contextmanager
    def main_log_extracted(self, server_id: Optional[UUID] = None) -> AbstractContextManager[Path]:
        if server_id is None:
            server_id = 'this'
        archive = self._http_download(f'rest/{self._version}/servers/{server_id}/logArchive', {
            'names': 'main',
            'rotated': 0,
            })
        with self._logs_extracted(archive) as logs:
            [main_log] = logs
            yield main_log

    def _get_camera_param_manifest(self, camera_id):
        return self.http_get(f'rest/{self._version}/devices/{str(camera_id)}/advanced/*/manifest')

    def _set_camera_advanced_params(self, camera_id, values):
        self.http_patch(
            path=f'rest/{self._version}/devices/{str(camera_id)}/advanced',
            data=values,
            )

    def get_static_web_content_info(self) -> Mapping[str, Any]:
        return self.http_get(
            f'rest/{self._version}/servers/this/staticWebContent',
            params=self._keep_default_params)

    def download_static_web_content(
            self, archive_url: str, sha256_hash: Optional[str] = None) -> Mapping[str, Any]:
        data = {'update': {'source': archive_url}}
        if sha256_hash is not None:
            data['update']['expectedSha256'] = sha256_hash
        self.http_put(f'rest/{self._version}/servers/this/staticWebContent', data)
        timeout_sec = 30
        started_at = time.monotonic()
        while True:
            response = self.get_static_web_content_info()
            update_info = response.get('update')
            if update_info is not None:
                status = update_info.get('status', '0')
                if status == 'ok':
                    percentage = update_info['percentage']
                    if percentage != 100:
                        raise RuntimeError(
                            f"Inappropriate status {status!r} with percentage {percentage!r}")
                    return response
                if status != '0':  # Status may be '0' if download is in progress
                    raise RuntimeError(
                        f"Failed to download Web Admin from {archive_url}. "
                        f"Status: {status}")
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Failed to download Web Admin from {archive_url} in {timeout_sec} seconds")
            time.sleep(1)

    def upload_static_web_content(self, archive: bytes):
        self._http_request(
            'PUT', f'rest/{self._version}/servers/this/staticWebContent/upload',
            headers={'Content-Type': 'application/octet-stream'},
            data=archive)

    def reset_static_web_content(self):
        self.http_delete(f'rest/{self._version}/servers/this/staticWebContent')

    def _dump_database(self):
        db_dump = self._http_download(f'rest/{self._version}/{self._site_term}/database')
        return db_dump

    def _restore_database(self, database):
        self._http_upload(f'rest/{self._version}/{self._site_term}/database', data=database)
