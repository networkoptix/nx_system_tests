# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections.abc import Collection
from typing import Any
from typing import Literal
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union
from uuid import UUID

from mediaserver_api import AuditTrail
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV3
from mediaserver_api._mediaserver import _format_uuid


class AuditTrailEventTypesV4(NamedTuple):
    CAMERA_INSERT = 'deviceInsert'
    CAMERA_REMOVE = 'deviceRemove'
    CAMERA_UPDATE = 'deviceUpdate'
    DATABASE_RESTORE = 'databaseRestore'
    EMAIL_SETTINGS = 'emailSettings'
    EVENT_RULE_REMOVE = 'eventRemove'
    EVENT_RULE_RESET = 'eventReset'
    EVENT_RULE_UPDATE = 'eventUpdate'
    EXPORT_VIDEO = 'exportVideo'
    LOGIN = 'login'
    NOT_DEFINED = 'notDefined'
    SERVER_REMOVE = 'serverRemove'
    SERVER_UPDATE = 'serverUpdate'
    SETTINGS_CHANGE = 'settingsChange'
    STORAGE_INSERT = 'storageInsert'
    STORAGE_REMOVE = 'storageRemove'
    STORAGE_UPDATE = 'storageUpdate'
    SITES_MERGE = 'siteMerge'
    SITE_NAME_CHANGED = 'siteNameChanged'
    UNAUTHORIZED_LOGIN = 'unauthorizedLogin'
    UPDATE_INSTALL = 'updateInstall'
    USER_REMOVE = 'userRemove'
    USER_UPDATE = 'userUpdate'
    VIEW_ARCHIVE = 'viewArchive'
    VIEW_LIVE = 'viewLive'


class MediaserverApiV4(MediaserverApiV3):

    _version = 'v4'
    _site_term = 'site'
    audit_trail_events = AuditTrailEventTypesV4

    @staticmethod
    def _get_search_id(raw_data) -> str:
        # Since VMS 6.1 search id contains server id and represents a string, not UUID.
        return raw_data['id']

    def add_dummy_smb_storage(self, index, parent_id=None):
        raise NotImplementedError("Unable to add storage using fake data in APIv4")

    def get_site_name(self) -> str:
        return self.get_system_settings()['siteName']

    @staticmethod
    def _get_duration_ms(period_raw):
        try:
            return int(period_raw['durationMs'])
        except KeyError:
            return None

    def _update_info_match(self, update_info):
        # Update info contains 'freeSpaceB' attribute, that is hard to calculate.
        from_mediaserver = {k: v for k, v in self._update_info().items() if k != 'freeSpaceB'}
        generated = {k: v for k, v in update_info.items() if k != 'freeSpaceB'}
        return from_mediaserver == generated

    update_status_literal = 'state'
    update_error_literal = 'error'

    def get_update_status(self, ignore_server_ids=()) -> Mapping[UUID, Mapping]:
        system_status = self._update_status()
        result = {}
        for server_id, status in system_status.items():
            server_id = UUID(server_id)
            if server_id in ignore_server_ids:
                continue
            result[server_id] = status
        return result

    def _start_update(self, update_info):
        self.http_post(f'rest/{self._version}/update/start', update_info)

    def _update_info(self):
        return self.http_get(f'rest/{self._version}/update/info')

    def _update_status(self):
        return self.http_get(f'rest/{self._version}/update')

    def cancel_update(self):
        self.http_delete(f'rest/{self._version}/update')

    @staticmethod
    def _prepare_update_info(update_info):
        return {
            'version': update_info['version'],
            'cloudHost': update_info['cloud_host'],
            'eulaLink': 'http://new.eula.com/eulaText',
            'eulaVersion': 1,
            'releaseNotesUrl': 'http://www.networkoptix.com/all-nx-witness-release-notes',
            'releaseDateMs': 0,
            'releaseDeliveryDays': 0,
            'description': '',
            'eula': '',
            'packages': {
                'server': [
                    MediaserverApiV4._prepare_package_info(p)
                    for p in update_info['packages']
                    ],
                },
            'url': '',
            'freeSpaceB': 0,
            'participants': [],
            'lastInstallationRequestTimeMs': -1,
            }

    @staticmethod
    def _prepare_package_info(package_info):
        return {
            'platform': package_info['platform'],
            'platformVariants': {},
            'file': package_info['file'],
            'md5': package_info['md5'],
            'sizeB': package_info['size'],
            'url': package_info['url'],
            'customClientVariant': '',
            'signature': package_info['signature'],
            }

    def list_audit_trail_records(self):
        response = self.http_get(f'rest/{self._version}/servers/this/audit')
        result = []
        for entry in response:
            if entry.get('details') is None:
                details = {}
                params = None
                resources = []
            else:
                details = entry['details']
                # Attributes 'version' and 'description' never go together.
                if 'version' in details:
                    params = 'version=' + details['version']
                elif 'description' in details:
                    params = 'description=' + details['description']
                else:
                    params = None
                if 'ids' in details:
                    resources = [UUID(res) for res in details['ids']]
                else:
                    resources = []
            record = AuditTrail.AuditRecord(
                type=entry['eventType'],
                params=params,
                resources=resources,
                created_time_sec=entry['createdTimeS'],
                range_start_sec=details.get('startS'),
                range_end_sec=details.get('endS'),
                )
            result.append(record)
        return result

    class MediaserverInfo(MediaserverApi.MediaserverInfo):

        def _parse_raw_data(self):
            return {
                'server_id': UUID(self._raw_data['id']),
                'local_site_id': UUID(self._raw_data['localSiteId']),
                'server_name': self._raw_data['name'],
                'site_name': self._raw_data['siteName'],
                'customization': self._raw_data['customization'],
                }

    def create_integration_request(
            self,
            integration_manifest: Mapping[str, Any],
            engine_manifest: Mapping[str, Any],
            pin_code: str,
            ) -> '_IntegrationRequest':
        body = {
            'integrationManifest': integration_manifest,
            'engineManifest': engine_manifest,
            'pinCode': pin_code,
            }
        raw_data = self.http_post(
            path=f'/rest/{self._version}/analytics/integrations/*/requests',
            data=body,
            )
        return _IntegrationRequest.from_raw(raw_data)

    def approve_integration_request(self, request_id: UUID) -> None:
        self.http_post(
            path=f'/rest/{self._version}/analytics/integrations/*/requests/{_format_uuid(request_id)}/approve',
            data={},
            )

    def _best_shot_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        # The endpoint is v3+, but it's only available on master, hence it belongs here.
        # See: https://networkoptix.atlassian.net/browse/VMS-54603
        # Forcing JPG format to make the return value consistent with MediaserverApiV0.
        return self._http_download(
            f'/rest/{self._version}/analytics/objectTracks/{track_id}/bestShotImage.jpg',
            params={'deviceId': camera_id},
            )

    def _title_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        # The endpoint is v3+, but it's only available on master, hence it belongs here.
        # See: https://networkoptix.atlassian.net/browse/VMS-54603
        # Forcing JPG format to make the return value consistent with MediaserverApiV0.
        return self._http_download(
            path=f'/rest/{self._version}/analytics/objectTracks/{track_id}/titleImage.jpg',
            params={
                'deviceId': camera_id,
                },
            )

    def _get_raw_metric_values(self):
        return self.http_get(f'rest/{self._version}/metrics/values')

    def get_filtered_raw_metric_values(self, *metric_path: str | UUID):
        # Note that the metric_path must match the path from the server response, for example:
        # [systems, *, info] and not [system_info].
        if metric_path:
            filters = '.'.join([str(path) for path in metric_path])
            return self.http_get(f'rest/{self._version}/metrics/values?_with={filters}')
        return self.http_get(f'rest/{self._version}/metrics/values')

    def _get_raw_metric_alarms(self):
        return self.http_get(f'rest/{self._version}/metrics/alarms')

    def execute_analytics_action(
            self,
            engine_id: UUID,
            action_id: str,
            object_track_id: UUID,
            camera_id: UUID,
            timestamp: int,
            params: Optional[Mapping] = None,
            ) -> Mapping[str, Union[str, bool]]:
        return self.http_post(
            path=(
                f'rest/{self._version}/analytics/engines/{_format_uuid(engine_id)}'
                f'/actions/{action_id}/execute'),
            data={
                'objectTrackId': _format_uuid(object_track_id),
                'deviceId': _format_uuid(camera_id),
                'timestampUs': str(timestamp * 1000),
                'parameters': params if params is not None else {},
                },
            )

    def _put_device_agent_settings(
            self,
            engine_id: UUID,
            device_id: UUID,
            settings: Mapping[str, Any],
            ):
        return self.http_put(
            path=(
                f'rest/{self._version}/analytics/engines/{_format_uuid(engine_id)}/'
                f'deviceAgents/{_format_uuid(device_id)}/settings'
                ),
            data=settings,
            )

    class DeviceAnalyticsSettings:

        def __init__(self, raw: Mapping):
            # Unlike v0, response does not contain settingsModel. Active settings
            # are not supported, hence no messageToUser here too.
            # See: https://networkoptix.atlassian.net/browse/VMS-52169
            self.values = raw['values']
            self.stream = raw['analyzedStream']

    def get_device_analytics_settings(self, device_id: UUID, engine_id: UUID):
        raw = self._put_device_agent_settings(
            engine_id=engine_id,
            device_id=device_id,
            settings={},
            )
        return self.DeviceAnalyticsSettings(raw)

    def set_device_analytics_settings(
            self,
            device_id: UUID,
            engine_id: UUID,
            settings_values: Mapping[str, Any],
            ):
        raw = self._put_device_agent_settings(
            engine_id=engine_id,
            device_id=device_id,
            settings={
                'values': settings_values,
                },
            )
        return self.DeviceAnalyticsSettings(raw)

    def set_device_analytics_analyzed_stream(
            self,
            device_id: UUID,
            engine_id: UUID,
            stream: Literal['primary', 'secondary'],
            ) -> None:
        self._put_device_agent_settings(
            engine_id=engine_id,
            device_id=device_id,
            settings={
                'analyzedStream': stream,
                'values': {},  # Stream selection only happens if "values" key is present.
                },
            )

    def _get_raw_analytics_engines(self):
        return self.http_get(f'/rest/{self._version}/analytics/engines')

    def get_actual_backup_state(self, camera_id: UUID):
        response = self.http_get(
            f'rest/{self._version}/servers/this/backupPositions/{_format_uuid(camera_id)}',
            self._keep_default_params)
        # Some fields were moved to the 'media' structure.
        # See: https://gitlab.nxvms.dev/dev/nx/-/merge_requests/27748
        # TODO: Remove the following line after merging the MR.
        media_data = response.get('media', response)
        # TODO: Uncomment the following line after merging the MR.
        # media_data = response['media']
        return self._BackupState(
            self._BackupPosition(media_data['positionHighMs'], media_data['positionLowMs']),
            self._ToBackup(response['toBackupHighMs'], response['toBackupLowMs']),
            media_data['bookmarkStartPositionMs'])

    def skip_all_backup_queues(self):
        current_timestamp_ms = self._get_timestamp_ms()
        response = self.http_get(
            f'rest/{self._version}/servers/this/backupPositions/', self._keep_default_params)
        # The structure has changed.
        # See: https://gitlab.nxvms.dev/dev/nx/-/merge_requests/27748
        if response is not None and 'media' in response[0]:
            self.http_put(
                f'rest/{self._version}/servers/this/backupPositions/',
                {
                    'media':
                        {
                            'positionHighMs': current_timestamp_ms,
                            'positionLowMs': current_timestamp_ms,
                            'bookmarkStartPositionMs': current_timestamp_ms,
                            },
                    'metadata': {},
                    },
                )
        else:
            # TODO: Remove this branch after merging MR27748.
            self.http_put(
                f'rest/{self._version}/servers/this/backupPositions/',
                {
                    'positionHighMs': current_timestamp_ms,
                    'positionLowMs': current_timestamp_ms,
                    'bookmarkStartPositionMs': current_timestamp_ms,
                    },
                )

    def has_public_ip(self) -> bool:
        return 'hasInternetConnection' in self._get_server_flags()

    def list_events(
            self,
            camera_id: UUID | str | None = None,
            type_: str | None = None,
            ) -> Collection[Mapping[str, Any]]:
        query = {
            'serverId': _format_uuid(self.get_server_id()),
            'startTimeMs': 0,
            'durationMs': None,
            'eventResourceId': [_format_uuid(camera_id)] if camera_id is not None else None,
            'eventType': type_,
            }
        return self.http_get(
            f'/rest/{self._version}/events/log',
            {k: v for k, v in query.items() if v is not None},
            timeout=90,
            )


class _IntegrationRequest:

    def __init__(self, request_id: UUID, user: str, password: str):
        self.id = request_id
        # TODO: Check if it is possible to make UserV3 object here.
        self._user = user
        self._password = password

    @classmethod
    def from_raw(cls, raw: Mapping[str, str]):
        return cls(UUID(raw['requestId']), raw['user'], raw['password'])

    def get_user_credentials(self) -> Sequence[str]:
        return [self._user, self._password]
