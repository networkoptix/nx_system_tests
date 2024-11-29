# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
import urllib.parse
from collections import defaultdict
from collections import namedtuple
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from enum import Enum
from typing import NamedTuple
from typing import Optional
from typing import Union
from uuid import UUID

from mediaserver_api._bookmarks import _BookmarkV1
from mediaserver_api._cameras import CameraV1
from mediaserver_api._groups import UserGroup
from mediaserver_api._http import HttpBearerAuthHandler
from mediaserver_api._http_exceptions import MediaserverApiHttpError
from mediaserver_api._http_exceptions import NotFound
from mediaserver_api._layouts import Layout
from mediaserver_api._mediaserver import Videowall
from mediaserver_api._mediaserver import _format_uuid
from mediaserver_api._mediaserver_v0 import MediaserverApiV0
from mediaserver_api._mediaserver_v0 import UserGroupNotFound
from mediaserver_api._merge_exceptions import CloudSystemsHaveDifferentOwners
from mediaserver_api._merge_exceptions import DependentSystemBoundToCloud
from mediaserver_api._merge_exceptions import IncompatibleCloud
from mediaserver_api._merge_exceptions import MergeDuplicateMediaserverFound
from mediaserver_api._servers import ServerV1
from mediaserver_api._storage import Storage
from mediaserver_api._storage import WrongPathError
from mediaserver_api._time_period import TimePeriod
from mediaserver_api._users import UserV1
from mediaserver_api._web_pages import WebPage

_logger = logging.getLogger(__name__)


class BackupContentType(Enum):
    bookmarks = 'bookmarks'
    motion = 'motion'
    objects = 'analytics'


class MediaserverApiV1(MediaserverApiV0):

    _preferred_auth_type = 'bearer'
    _version = 'v1'
    _site_term = 'system'
    _keep_default_params = {'_keepDefault': 'true'}

    @staticmethod
    def _prepare_data(data, key_mapping):
        prepared_data = defaultdict(dict)
        for key, value in data.items():
            if key in key_mapping:
                try:
                    [first_key, second_key] = key_mapping[key]
                except ValueError:
                    [new_key] = key_mapping[key]
                    prepared_data[new_key] = value
                else:
                    prepared_data[first_key][second_key] = value
            else:
                prepared_data[key] = value
        return prepared_data

    def add_web_page(self, name, url):
        response = self.http_post(
            f'rest/{self._version}/webPages', {'name': name, 'url': url})
        return UUID(response['id'])

    def list_web_pages(self):
        return [WebPage(data) for data in self.http_get(f'rest/{self._version}/webPages')]

    def get_web_page(self, page_id):
        try:
            web_page_data = self.http_get(
                f'rest/{self._version}/webPages/{_format_uuid(page_id, strict=True)}')
        except NotFound:
            return None
        return WebPage(web_page_data)

    def modify_web_page(self, page_id, name=None, url=None):
        self.http_patch(
            f'rest/{self._version}/webPages/{_format_uuid(page_id, strict=True)}',
            self._prepare_params({'name': name, 'url': url}))

    def remove_web_page(self, page_id):
        self.http_delete(f'rest/{self._version}/webPages/{_format_uuid(page_id, strict=True)}')

    def add_bookmark(self, camera_id, name, start_time_ms=0, duration_ms=60000, description=None):
        request_data = {
            'name': name,
            'startTimeMs': str(start_time_ms),
            'durationMs': str(duration_ms),
            }
        if description:
            request_data['description'] = description
        response = self.http_post(
            f'rest/{self._version}/devices/{_format_uuid(camera_id)}/bookmarks', request_data)
        bookmark = _BookmarkV1(response)
        return bookmark.id

    def list_bookmarks(self, camera_id):
        bookmarks_data = self.http_get(
            f'rest/{self._version}/devices/{_format_uuid(camera_id)}/bookmarks',
            self._keep_default_params)
        return [_BookmarkV1(data) for data in bookmarks_data]

    def get_bookmark(self, camera_id, bookmark_id):
        camera_id = _format_uuid(camera_id, strict=True)
        bookmark_id = _format_uuid(bookmark_id, strict=True)
        try:
            bookmark_data = self.http_get(
                f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark_id}',
                self._keep_default_params)
        except NotFound:
            return None
        return _BookmarkV1(bookmark_data)

    def set_bookmark_duration(self, bookmark: _BookmarkV1, duration_ms):
        # Need all values to update bookmark.
        camera_id = _format_uuid(bookmark.camera_id, strict=True)
        bookmark_id = _format_uuid(bookmark.id, strict=True)
        self.http_patch(f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark_id}', {
            'name': bookmark.name,
            'startTimeMs': str(bookmark.start_time_ms),
            'durationMs': str(duration_ms),
            })

    def remove_bookmark(self, bookmark: _BookmarkV1):
        bookmark_id = _format_uuid(bookmark.id, strict=True)
        self.http_delete(f'rest/{self._version}/devices/*/bookmarks/{bookmark_id}')

    def update_bookmark_description(self, camera_id, bookmark_id, new_description):
        camera_id = _format_uuid(camera_id, strict=True)
        bookmark_id = _format_uuid(bookmark_id, strict=True)
        self.http_patch(f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark_id}', {
            'description': new_description,
            })

    def _get_servers_timestamp(self):
        return [info['synchronizedTimeMs'] for info in self.http_get(
            f'rest/{self._version}/servers/*/info')]

    def _add_layout(self, primary):
        if 'id' in primary:
            layout_id = primary['id']
            response = self.http_put(f'rest/{self._version}/layouts/{layout_id}', primary)
        else:
            response = self.http_post(f'rest/{self._version}/layouts', primary)
        return UUID(response['id'])

    def add_layout(self, name, type_id=None):
        if type_id is None:
            type_id = self._layout_type_id
        data = {
            'name': name,
            'typeId': _format_uuid(type_id, strict=True),
            'items': [],
            'fixedWidth': 0,
            'fixedHeight': 0,
            # If parentId of layout is specified, this layout is only available to the user
            # whose ID is specified in parentId. If the parentId value is not passed in the request,
            # it will be automatically set with the request's user id. To make the layout shared,
            # the parentId value must be passed as a nil UUID
            'parentId': str(UUID(int=0)),
            }
        return self._add_layout(data)

    def list_layouts(self):
        response = self.http_get(f'rest/{self._version}/layouts', self._keep_default_params)
        return [Layout(layout_data) for layout_data in response]

    def get_layout(self, layout_id):
        try:
            response = self.http_get(
                f'rest/{self._version}/layouts/{_format_uuid(layout_id, strict=True)}',
                self._keep_default_params)
        except NotFound:
            return None
        return Layout(response)

    def remove_layout(self, layout_id):
        self.http_delete(f'rest/{self._version}/layouts/{_format_uuid(layout_id, strict=True)}')

    _camera_key_mapping = {
        'scheduleTasks': ('schedule', 'tasks'),
        'scheduleEnabled': ('schedule', 'isEnabled'),
        'motionMask': ('motion', 'mask'),
        'motionType': ('motion', 'type'),
        'recordAfterMotionSec': ('motion', 'recordAfterS'),
        'recordBeforeMotionSec': ('motion', 'recordBeforeS'),
        'audioEnabled': ('options', 'isAudioEnabled'),
        'preferredServerId': ('options', 'preferredServerId'),
        'minArchiveDays': ('schedule', 'minArchiveDays'),  # vms_5.0 and earlier
        'maxArchiveDays': ('schedule', 'maxArchiveDays'),  # vms_5.0 and earlier
        'minArchivePeriodS': ('schedule', 'minArchivePeriodS'),  # vms_5.0_patch
        'maxArchivePeriodS': ('schedule', 'maxArchivePeriodS'),  # vms_5.0_patch
        'parentId': ('serverId',),
        'backupPolicy': ('options', 'backupPolicy'),
        'backupQuality': ('options', 'backupQuality'),
        'backupContentType': ('options', 'backupContentType'),
        }

    def _add_camera(self, primary):
        prepared_data = self._prepare_data(primary, self._camera_key_mapping)
        if 'id' in prepared_data:
            camera_id = prepared_data['id']
            response = self.http_put(f'rest/{self._version}/devices/{camera_id}', prepared_data)
        else:
            response = self.http_post(f'rest/{self._version}/devices', prepared_data)
        return UUID(response['id'])

    def add_generated_camera(self, primary, attributes=None, params=None):
        if attributes is None:
            attributes = {}
        if params is None:
            params = {}
        self._add_camera({**primary, **attributes, 'parameters': params})

    def list_cameras(self):
        cameras = self.http_get(
            f'rest/{self._version}/devices', self._keep_default_params, timeout=90)
        return [CameraV1(camera_data) for camera_data in cameras]

    def get_camera(self, camera_id, is_uuid=True, validate_logical_id=True):
        camera_id = self._format_camera_id(camera_id, is_uuid, validate_logical_id)
        try:
            data = self.http_get(f'rest/{self._version}/devices/{camera_id}', self._keep_default_params)
        except NotFound:
            return None
        return CameraV1(data)

    def _modify_camera(self, camera_id, data):
        prepared_attributes = self._prepare_data(data, self._camera_key_mapping)
        self.http_patch(
            f'rest/{self._version}/devices/{_format_uuid(camera_id)}', prepared_attributes)

    class RecordedPeriodsType(NamedTuple):

        RECORDING = 'recording'
        MOTION = 'motion'
        ANALYTICS = 'analytics'

    def _list_recorded_periods(self, camera_ids, periods_type=None, detail_level_ms=None):
        periods = {}
        params = {}
        if periods_type is not None:
            params['periodType'] = periods_type
        if detail_level_ms is not None:
            params['detailLevelMs'] = detail_level_ms
        for camera_id in camera_ids:
            camera_periods = self.http_get(
                f'rest/{self._version}/devices/{camera_id}/footage', params)
            periods[camera_id] = camera_periods
        return periods

    def list_recorded_periods_server_ids(self, camera_id):
        # Get periods 'serverId' attribute (APIv1 only).
        [periods] = self._list_recorded_periods([camera_id]).values()
        return {UUID(p['serverId']) for p in periods}

    def _save_camera_attributes(self, camera_id, attributes):
        self._modify_camera(camera_id, attributes)

    def _save_camera_attributes_list(self, camera_ids, attributes):
        for camera_id in camera_ids:
            self._save_camera_attributes(camera_id, attributes)

    def rename_camera(self, camera_id, new_name):
        # Unlike the old API, new REST API can be used to set the value of 'name' directly. There's
        # no 'cameraName' field available for REST API
        self._modify_camera(camera_id, {'name': new_name})

    def _start_manual_cameras_search(self, camera_url, credentials):
        data = {'ip': camera_url}
        if credentials:
            data['credentials'] = credentials
        response = self.http_post(f'rest/{self._version}/devices/*/searches', data)
        return UUID(response['id'])

    def _get_manual_cameras_search_state(self, search_id):
        response = self.http_get(f'rest/{self._version}/devices/*/searches/{search_id}')
        manual_cameras = {camera['physicalId']: camera for camera in response.get('devices', [])}
        status = response['status']
        return manual_cameras, status

    def _add_manual_cameras_to_db(self, searcher_camera_list, credentials):
        # Credentials should be in searcher_camera_list
        for camera_params in searcher_camera_list:
            self._add_camera(camera_params)

    def add_manual_camera_sync(
            self,
            camera_url: str,
            user: Optional[str] = None,
            password: Optional[str] = None,
            ):
        data = {
            'mode': 'addFoundDevices',
            'target': {
                'ip': camera_url,
                },
            }
        credentials = self._make_camera_auth_params(user, password)
        if credentials:
            data['credentials'] = credentials
        response = self.http_post(
            path=f'/rest/{self._version}/devices/*/searches',
            data=data,
            )
        devices = response['devices']
        all_cameras = {c.id: c for c in self.list_cameras()}
        return [all_cameras[UUID(device_data['id'])] for device_data in devices]

    def _set_camera_streams(self, camera_id: UUID, primary_stream_url: str, secondary_stream_url: str):
        self.http_patch(
            f'rest/{self._version}/devices/{camera_id}',
            {'parameters': {'streamUrls': {'1': primary_stream_url, '2': secondary_stream_url}}})

    def remove_camera(self, camera_id):
        self.http_delete(f'rest/{self._version}/devices/{camera_id}')

    _server_key_mapping = {
        'backupType': ('backupSettings', 'type'),
        'backupDaysOfTheWeek': ('backupSettings', 'daysOfTheWeek'),
        'backupStart': ('backupSettings', 'autoStartTimeS'),
        'backupDuration': ('backupSettings', 'durationS'),
        'backupBitrate': ('backupSettings', 'bitrateBps'),
        }

    def _add_mediaserver(self, data):
        prepared_data = self._prepare_data(data, self._server_key_mapping)
        if 'id' in data:
            server_id = prepared_data['id']
            response = self.http_put(f'rest/{self._version}/servers/{server_id}', prepared_data)
        else:
            response = self.http_post(f'rest/{self._version}/servers', prepared_data)
        return UUID(response['id'])

    def add_dummy_mediaserver(self, index):
        data = self._make_dummy_mediaserver_data(index)
        return self._add_mediaserver(data)

    def add_generated_mediaserver(self, primary, attributes=None):
        if attributes is None:
            attributes = {}
        self._add_mediaserver({**primary, **attributes})

    def _get_timestamp_ms(self) -> int:
        return self.http_get(f'rest/{self._version}/servers/this/info')['synchronizedTimeMs']

    def request_restart(self):
        self.http_post(f'rest/{self._version}/servers/this/restart', {})

    def list_servers(self):
        return [
            ServerV1(data) for data in self.http_get(
                f'rest/{self._version}/servers', self._keep_default_params)]

    def get_server(self, server_id):
        url = f'rest/{self._version}/servers/{_format_uuid(server_id)}'
        try:
            data = self.http_get(url, self._keep_default_params)
        except NotFound:
            return None
        return ServerV1(data)

    def _modify_server(self, server_id, data):
        prepared_data = self._prepare_data(data, self._server_key_mapping)
        self.http_patch(f'rest/{self._version}/servers/{_format_uuid(server_id)}', prepared_data)

    def _save_server_attributes(self, server_id, attributes):
        self._modify_server(server_id, attributes)

    def rename_server(self, new_server_name, server_id=None):
        if server_id is None:
            server_id = self.get_server_id()
        self._modify_server(server_id, {'name': new_server_name})

    def remove_server(self, server_id):
        self.http_delete(f'rest/{self._version}/servers/{_format_uuid(server_id)}')

    def _get_server_info(self):
        return self.http_get(f'rest/{self._version}/servers/this/info')

    # noinspection PyMethodOverriding
    def get_module_info(self):
        return self.http_get(f'rest/{self._version}/servers/this/info')

    @staticmethod
    def _prepare_storage_data(primary):
        api_v0_storage_fields = ('usedForWriting', 'url', 'spaceLimit', 'storageType')
        prepared_primary = {k: v for k, v in primary.items() if k not in api_v0_storage_fields}
        if 'usedForWriting' in primary:
            prepared_primary['isUsedForWriting'] = primary['usedForWriting']
        if 'url' in primary:
            prepared_primary['path'] = primary['url']
        if 'spaceLimit' in primary:
            prepared_primary['spaceLimitB'] = int(primary['spaceLimit'])
        if 'storageType' in primary:
            prepared_primary['type'] = primary['storageType']
        return prepared_primary

    def _add_storage(self, primary):
        prepared_primary = self._prepare_storage_data(primary)
        if 'id' in prepared_primary:
            response = self.http_put(
                f'rest/{self._version}/servers/this/storages/{prepared_primary["id"]}',
                prepared_primary)
        else:
            response = self.http_post(
                f'rest/{self._version}/servers/this/storages', prepared_primary)
        return UUID(response['id'])

    def add_storage(self, path_or_url, storage_type, is_backup=False):
        try:
            return self._add_storage({
                'isBackup': is_backup,
                'isUsedForWriting': True,
                'name': path_or_url.split('/')[-1],
                'path': path_or_url,
                'storageType': storage_type,
                })
        except MediaserverApiHttpError as e:
            if "Access denied" in e.vms_error_string:
                raise PermissionError(f"Wrong credentials: {path_or_url}")
            if re.match(r'Invalid parameter [\'`]path[\'`]', e.vms_error_string) is not None:
                raise WrongPathError(f"Wrong path: {path_or_url}")
            raise e

    def add_dummy_smb_storage(self, index, parent_id=None):
        raise NotImplementedError("Unable to add storage using fake data in APIv1")

    def _list_storage_objects(self):
        storages = self.http_get(
            f'rest/{self._version}/servers/this/storages/*/status', self._keep_default_params)
        return [Storage(data) for data in storages]

    def list_all_storages(self):
        storages = self.http_get(
            f'rest/{self._version}/servers/*/storages/*/status', self._keep_default_params)
        return [Storage(data) for data in storages]

    def get_metadata_storage_id(self):
        server = self.http_get(f'rest/{self._version}/servers/this', self._keep_default_params)
        # metadataStorageId has no default and therefore may be missing.
        metadata_storage_id = server['parameters'].get('metadataStorageId')
        if metadata_storage_id is None:
            return None
        return UUID(metadata_storage_id)

    def get_storage(self, storage_id: UUID):
        storage_id = _format_uuid(storage_id, strict=True)
        try:
            storage_data = self.http_get(
                f'rest/{self._version}/servers/this/storages/{_format_uuid(storage_id)}/status',
                self._keep_default_params)
        except NotFound:
            return None
        return Storage(storage_data)

    def _modify_storage(self, storage_id, primary):
        storage_id = _format_uuid(storage_id)
        prepared_primary = self._prepare_storage_data(primary)
        self.http_patch(f'rest/{self._version}/servers/this/storages/{storage_id}', prepared_primary)

    def allocate_storage_for_analytics(self, storage_id):
        storage_id = _format_uuid(storage_id)
        self.http_patch(
            f'rest/{self._version}/servers/this', {'parameters': {'metadataStorageId': storage_id}})

    def remove_storage(self, storage_id):
        _logger.debug("Remove storage: %s", storage_id)
        storage_id = _format_uuid(storage_id, strict=True)
        self.http_delete(f'rest/{self._version}/servers/this/storages/{storage_id}')

    def _add_user(self, primary):
        if 'id' in primary:
            response = self.http_put(f'rest/{self._version}/users/{primary["id"]}', primary)
        else:
            response = self.http_post(f'rest/{self._version}/users', primary)
        return UUID(response['id'])

    def _prepare_auth_params(self, name, password):
        # Setting password using hashed data is not working for /rest/v1/users endpoint.
        # Password must be send as string. <name> is not required anymore for auth params.
        return {'password': password}

    def _make_local_user_primary_params(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ):
        return self._prepare_params({
            'name': name,
            'permissions': self._format_permissions(permissions),
            'userRoleId': _format_uuid(group_id) if group_id is not None else None,
            'type': 'local',
            })

    def _make_cloud_user_primary_params(
            self,
            name: str,
            email: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ):
        return self._prepare_params({
            'name': name,
            'email': email,
            'permissions': self._format_permissions(permissions),
            'userRoleId': _format_uuid(group_id) if group_id is not None else None,
            'type': 'cloud',
            })

    def _make_ldap_user_primary_params(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            full_name: Optional[str] = None,
            email: Optional[str] = None,
            enable_basic_and_digest_auth: Optional[bool] = False,
            dn: Optional[str] = None,
            ):
        if dn is not None:
            # Since VMS-37062 externalId is an object.
            if not self.server_older_than('vms_6.0'):
                dn = {
                    'dn': dn,
                    'synced': True,
                    }
        return self._prepare_params({
            'name': name,
            'permissions': self._format_permissions(permissions),
            'fullName': full_name,
            'email': email,
            'isHttpDigestEnabled': True if enable_basic_and_digest_auth else None,
            'externalId': dn,
            'type': 'ldap',
            })

    def list_users(self) -> Collection[UserV1]:
        users = self.http_get(f'rest/{self._version}/users', self._keep_default_params)
        return [UserV1(data) for data in users]

    def get_user(self, user_id):
        try:
            user_data = self.http_get(
                f'rest/{self._version}/users/{_format_uuid(user_id)}', self._keep_default_params)
        except NotFound:
            return None
        return UserV1(user_data)

    def _modify_user(self, user_id, primary):
        self.http_patch(f'rest/{self._version}/users/{_format_uuid(user_id)}', {**primary})

    def set_user_password(self, user_id, password):
        self._modify_user(user_id, {'password': password})

    def set_user_credentials(self, user_id, name, password):
        self._modify_user(user_id, {'name': name, 'password': password})

    def remove_user(self, user_id):
        self.http_delete(f'rest/{self._version}/users/{_format_uuid(user_id)}')

    def set_user_access_rights(self, user_id, resource_ids, access_type=None):
        params = self._prepare_params({
            'accessibleResources': [_format_uuid(_id) for _id in resource_ids],
            })
        self.http_patch(f'rest/{self._version}/users/{_format_uuid(user_id)}', params)

    def _add_user_group(self, primary):
        if 'id' in primary:
            group_id = primary['id']
            response = self.http_put(f'rest/{self._version}/userRoles/{group_id}', primary)
        else:
            response = self.http_post(f'rest/{self._version}/userRoles', primary)
        return UUID(response['id'])

    def get_user_group(self, group_id):
        try:
            user_group_data = self.http_get(
                f'rest/{self._version}/userRoles/{_format_uuid(group_id)}',
                self._keep_default_params)
        except NotFound:
            raise UserGroupNotFound(f"Group {group_id} is not found")
        return UserGroup(user_group_data)

    def _modify_user_group(self, group_id, primary):
        self.http_patch(f'rest/{self._version}/userRoles/{_format_uuid(group_id)}', primary)

    def remove_user_group(self, group_id):
        self.http_delete(f'rest/{self._version}/userRoles/{_format_uuid(group_id)}')

    def set_group_access_rights(self, group_id, resource_ids):
        params = self._prepare_params({
            'accessibleResources': [_format_uuid(_id) for _id in resource_ids],
            })
        self.http_patch(f'rest/{self._version}/userRoles/{group_id}', params)

    def _get_version(self):
        return self.http_get(f'rest/{self._version}/servers/this/info')['version']

    def _make_cloud_setup_request(
            self, system_name, cloud_system_id, auth_key, account_name, system_settings):
        formatted_settings = self._format_system_settings(system_settings)
        self.http_post(f'rest/{self._version}/{self._site_term}/setup', {
            'name': system_name,
            'settings': formatted_settings,
            'cloud': {
                'systemId': cloud_system_id,
                'authKey': auth_key,
                'owner': account_name,
                },
            })

    def connect_system_to_cloud(self, auth_key, system_id, user_email):
        self.http_post(f'rest/{self._version}/{self._site_term}/cloudBind', {
            'authKey': auth_key,
            'systemId': system_id,
            'owner': user_email,
            })

    def _detach_from_cloud(self, password, current_password):
        self.http_post(f'rest/{self._version}/{self._site_term}/cloudUnbind', {'password': password})

    def _make_local_setup_request(self, system_name, password, system_settings, settings_preset):
        formatted_settings = self._format_system_settings(system_settings)
        data = {
            'name': system_name,
            'settings': formatted_settings,
            'local': {'password': password},
            }
        if settings_preset is not None:
            data['settingsPreset'] = settings_preset
        self.http_post(f'rest/{self._version}/{self._site_term}/setup', data)

    def _detach_from_system(self):
        self.http_post(f'rest/{self._version}/servers/this/detach', {})

    @property
    def _version_specific_system_settings(self):
        if self.specific_features().get('sessionLimitS') > 0:
            session_limit_name = 'sessionLimitS'
            session_limit_value = 365 * 24 * 3600
        else:
            session_limit_name = 'sessionLimitMinutes'
            session_limit_value = 365 * 24 * 60
        return {
            # Set session limits to one year to avoid session token expired errors during tests
            session_limit_name: session_limit_value,
            }

    def get_system_settings(self):
        settings = self.http_get(f'rest/{self._version}/{self._site_term}/settings', self._keep_default_params)
        extracted_settings = {}
        for key, value in settings.items():
            if isinstance(value, bool):
                extracted_settings[key] = str(value).lower()
            else:
                extracted_settings[key] = value
        return extracted_settings

    def set_system_settings(self, new_settings):
        formatted_settings = self._format_system_settings(new_settings)
        self.http_patch(f'rest/{self._version}/{self._site_term}/settings', formatted_settings)

    def get_local_system_id(self):
        return UUID(self.http_get(f'rest/{self._version}/{self._site_term}/info')['localId'])

    def merge_in_progress(self, timeout_sec):
        status = self.http_get(
            f'rest/{self._version}/{self._site_term}/merge',
            params=self._keep_default_params,
            timeout=timeout_sec)
        return status['mergeInProgress']

    def get_auth_data(self) -> str:
        if not isinstance(self._auth_handler, HttpBearerAuthHandler):
            raise RuntimeError(
                f"The {self.auth_type!r} authentication scheme is used, but since APIv1 "
                f"merge is only possible using session tokens")
        return self._auth_handler.get_token()

    class _SessionInfo(NamedTuple):
        age_sec: int
        expires_in_sec: int

    def get_session_info(self, token: str) -> _SessionInfo:
        response = self.http_get(
            f'rest/{self._version}/login/sessions/{token}', self._keep_default_params)
        return self._SessionInfo(age_sec=response['ageS'], expires_in_sec=response['expiresInS'])

    def remove_session(self, token):
        self.http_delete(f'rest/{self._version}/login/sessions/{token}')

    def _request_merge(
            self,
            remote_url: str,
            remote_auth: str,
            take_remote_settings=False,
            merge_one_server=False):
        remote_socket_address = urllib.parse.urlparse(remote_url).netloc
        try:
            return self.http_post(f'rest/{self._version}/{self._site_term}/merge', {
                'remoteEndpoint': remote_socket_address,
                'remoteSessionToken': remote_auth,
                'takeRemoteSettings': take_remote_settings,
                'mergeOneServer': merge_one_server,
                })
        except MediaserverApiHttpError as e:
            different_owners_regexp = re.compile(r'Cannot merge two( Nx)? Cloud (Systems|Sites) with different owners')
            if different_owners_regexp.search(e.vms_error_string):
                raise CloudSystemsHaveDifferentOwners(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            system_bound_to_cloud_error = 'Cannot merge systems bound to the Cloud'  # For VMS 5.1
            system_bound_to_cloud_regexp = re.compile(
                r'prohibited to merge a( Nx)? Cloud (System|system|Site), with a (System|system|Site) not connected to( Nx)? Cloud, '
                r'that is the (System|system|Site) from which the (System|system|Site) name and settings are taken')
            if system_bound_to_cloud_error in e.vms_error_string or system_bound_to_cloud_regexp.search(e.vms_error_string):
                raise DependentSystemBoundToCloud(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            incompatible_cloud_host_regexp = re.compile(r'Incompatible (system|Site)( Nx)? Cloud host')
            if incompatible_cloud_host_regexp.search(e.vms_error_string):
                raise IncompatibleCloud(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            equal_id_regexp = re.compile(r'(System|Site) that has Server with id equal to this Server id')
            same_server_regexp = re.compile(r'Both (systems|Sites) have same server')
            if equal_id_regexp.search(e.vms_error_string) or same_server_regexp.search(e.vms_error_string):
                raise MergeDuplicateMediaserverFound(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            raise

    @staticmethod
    def _prepare_videowall_data(data):
        prepared = {k: v for k, v in data.items()}
        prepared.setdefault('autorun', True)
        prepared.setdefault('timeline', True)
        prepared.setdefault('items', [])
        prepared.setdefault('screens', [])
        prepared.setdefault('matrices', [])
        return prepared

    def _add_videowall(self, primary):
        prepared_primary = self._prepare_videowall_data(primary)
        videowall_id = prepared_primary.get('id')
        if videowall_id is not None:
            response = self.http_put(
                f'rest/{self._version}/videoWalls/{_format_uuid(videowall_id)}',
                prepared_primary)
        else:
            response = self.http_post(f'rest/{self._version}/videoWalls', prepared_primary)
        return UUID(response['id'])

    def remove_videowall(self, videowall_id):
        self.http_delete(f'rest/{self._version}/videoWalls/{_format_uuid(videowall_id)}')

    def list_videowalls(self):
        response = self.http_get(f'rest/{self._version}/videoWalls', self._keep_default_params)
        return [Videowall(data) for data in response]

    def _request_with_required_authentication(self):
        self.http_get(f'rest/{self._version}/servers/this')

    def refresh_session(self):
        # For now, this method is only required when using websockets.
        # TODO: Use auth handler in websockets.
        if not isinstance(self._auth_handler, HttpBearerAuthHandler):
            raise RuntimeError("Bearer authentication only uses sessions")
        self._auth_handler.refresh_token()

    def change_cameras_group_name(self, camera_ids, new_group_name):
        self._save_camera_attributes_list(camera_ids, {'group': {'name': new_group_name}})

    def add_license(self, license_key: str, license_block: str):
        # PUT rest/v1/licenses/{key} do not activate license if license block is present
        self.http_put(
            f'rest/{self._version}/licenses/{license_key}', {'licenseBlock': license_block})

    def _activate_license(self, license_key: str):
        self.http_put(f'rest/{self._version}/licenses/{license_key}', {})

    def remove_license(self, license_key: str):
        self.http_delete(f'rest/{self._version}/licenses/{license_key}')

    def _list_licenses(self):
        return self.http_get(f'rest/{self._version}/licenses')

    def _get_server_flags(self):
        return self.http_get(f'rest/{self._version}/servers/this/info')['serverFlags']

    def _dump_database(self):
        database = self.http_get(f'rest/{self._version}/{self._site_term}/database')['data']
        return database.encode('ascii')

    def _restore_database(self, database):
        base64_backup_data_str = database.decode('ascii')
        self.http_post(f'rest/{self._version}/{self._site_term}/database', {'data': base64_backup_data_str})

    _BackupPosition = namedtuple('_BackupPosition', 'high_ms low_ms')
    _ToBackup = namedtuple('_ToBackup', 'high_ms low_ms')
    _BackupState = namedtuple('_BackupState', 'position to_backup bookmark_start_position_ms')

    def get_actual_backup_state(self, camera_id):
        response = self.http_get(
            f'rest/{self._version}/servers/this/backupPositions/{_format_uuid(camera_id)}',
            self._keep_default_params)
        return self._BackupState(
            self._BackupPosition(response['positionHighMs'], response['positionLowMs']),
            self._ToBackup(response['toBackupHighMs'], response['toBackupLowMs']),
            response['bookmarkStartPositionMs'])

    def wait_for_backup_finish(self):
        timeout_sec = 90
        started_at = time.monotonic()
        server_id = self.get_server_id()
        server_cameras = [
            c for c in self.list_cameras() if c.parent_id == server_id]
        positions = {c.id: self._BackupPosition(0, 0) for c in server_cameras}
        while True:
            backup_finished = True
            for camera in server_cameras:
                state = self.get_actual_backup_state(camera.id)
                if state.to_backup > (0, 0):
                    _logger.debug("toBackupMs is not zero for %s: %s", camera, state.to_backup)
                    backup_finished = False
                    continue  # No point in checking position if toBackupMs is not zero yet.
                # toBackup<High/Low>Ms intended to show if backup is finished or not, but
                # position<High/Low>Ms can change for some time after <High/Low>Ms is zero,
                # see https://networkoptix.atlassian.net/browse/VMS-22795
                # We must ensure that position is not changing before proceed further.
                previous_position = positions[camera.id]
                if state.position > previous_position:
                    _logger.debug(
                        "Backup position changes for camera %s from %s to %s",
                        camera, previous_position, state.position)
                    positions[camera.id] = state.position
                    backup_finished = False
            if backup_finished:
                return
            if time.monotonic() - started_at > timeout_sec:
                raise TimeoutError("Archive didn't back up after timeout")
            time.sleep(2)

    def wait_for_backup_state_changed(self, camera_id, timeout_sec=1):
        # TODO: Replace with wait_for_backup_progress() if possible
        started_at = time.monotonic()
        initial_state = self.get_actual_backup_state(camera_id)
        while True:
            if initial_state != self.get_actual_backup_state(camera_id):
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError("Waiting for backup state changed is timed out")
            _logger.debug("Waiting for backup state of camera %s changed", camera_id)
            time.sleep(0.1)

    def wait_for_backup_progress(self, camera_id):
        timeout_sec = 5
        started_at = time.monotonic()
        initial_state = self.get_actual_backup_state(camera_id)
        while True:
            if initial_state.position < self.get_actual_backup_state(camera_id).position:
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(f"Waiting for backup progress for camera {camera_id} timed out")
            _logger.debug("Waiting for backup progress for camera %s changed", camera_id)
            time.sleep(0.1)

    def _enable_failover(self, max_cameras):
        self.http_patch(f'rest/{self._version}/servers/this', {
            'isFailoverEnabled': True,
            'maxCameras': max_cameras,
            })

    def _get_backup_settings(self):
        return self.http_get(
            f'rest/{self._version}/servers/this/backupSettings', self._keep_default_params)

    def _set_backup_quality_for_newly_added_cameras(self, low: bool, high: bool):
        default_settings = self._get_backup_settings()
        # 0 (high and low), 1 (high), 2 (low).
        quality = 0 if high and low else high + (low << 1)
        self.http_post(f'rest/{self._version}/servers/this/backupSettings', {
            'backupNewCameras': default_settings['backupNewCameras'],  # Required parameter
            'quality': str(quality),
            })

    def _set_backup_for_newly_added_cameras(self, enabled: bool):
        default_settings = self._get_backup_settings()
        self.http_post(f'rest/{self._version}/servers/this/backupSettings', {
            'backupNewCameras': enabled,
            'quality': default_settings['quality'],  # Required parameter
            })

    def enable_backup_for_newly_added_cameras(self):
        self._set_backup_for_newly_added_cameras(True)

    def disable_backup_for_newly_added_cameras(self):
        self._set_backup_for_newly_added_cameras(False)

    def _restore_state(self):
        self.http_post(f'rest/{self._version}/servers/this/reset', {})

    def limit_backup_bandwidth(self, bytes_per_sec: int):
        schedule = []
        for day in self._weekdays:
            for hour in range(24):
                schedule.append({'key': {'day': day, 'hour': hour}, 'value': bytes_per_sec})
        self._save_server_attributes(
            self.get_server_id(),
            {'backupBitrateBytesPerSecond': schedule})

    def set_unlimited_backup_bandwidth(self):
        self._save_server_attributes(self.get_server_id(), {'backupBitrateBytesPerSecond': []})

    def limit_backup_bandwidth_by_schedule(self, day: str, hour: int, bytes_per_sec: int):
        schedule = []
        for weekday in self._weekdays:
            for weekday_hour in range(24):
                if day == weekday and hour == weekday_hour:
                    schedule.append(
                        {'key': {'day': weekday, 'hour': weekday_hour}, 'value': bytes_per_sec})
                else:
                    # See: https://networkoptix.testrail.net/index.php?/cases/view/85909
                    schedule.append(
                        {'key': {'day': weekday, 'hour': weekday_hour}, 'value': 0})
        self._save_server_attributes(
            self.get_server_id(), {'backupBitrateBytesPerSecond': schedule})

    def skip_current_backup_queue(self, camera_id):
        current_timestamp_ms = self._get_timestamp_ms()
        self.http_put(
            f'rest/{self._version}/servers/this/backupPositions/{_format_uuid(camera_id)}',
            {
                'positionHighMs': current_timestamp_ms,
                'positionLowMs': current_timestamp_ms,
                'bookmarkStartPositionMs': current_timestamp_ms,
                })

    def set_backup_all_archive(self, camera_id: str):
        self._modify_camera(camera_id, {'backupContentType': 'archive'})

    def set_backup_content_type(self, camera_id: UUID, content_types: Sequence[BackupContentType]):
        backup_content_type = '|'.join([content_type.value for content_type in content_types])
        self._modify_camera(camera_id, {'backupContentType': backup_content_type})

    def skip_all_backup_queues(self):
        current_timestamp_ms = self._get_timestamp_ms()
        self.http_put(
            f'rest/{self._version}/servers/this/backupPositions/',
            {
                'positionHighMs': current_timestamp_ms,
                'positionLowMs': current_timestamp_ms,
                'bookmarkStartPositionMs': current_timestamp_ms,
                })

    def merge_is_finished(
            self,
            merge_responses,
            merge_timeout_sec,
            ):
        timeout_sec = max(20., merge_timeout_sec / 10)
        if self.merge_in_progress(timeout_sec=timeout_sec):
            _logger.info("Merge is in progress on %s", self)
            return False
        return True

    def backup_is_enabled_for_newly_added_cameras(self):
        settings = self._get_backup_settings()
        return settings['backupNewCameras']

    _BackupQuality = namedtuple('_BackupQuality', 'low high')

    @classmethod
    def _parse_backup_quality(cls, backup_quality: str):
        if backup_quality == 'CameraBackupBoth':
            return cls._BackupQuality(low=True, high=True)
        elif backup_quality == 'CameraBackupLowQuality':
            return cls._BackupQuality(low=True, high=False)
        elif backup_quality == 'CameraBackupHighQuality':
            return cls._BackupQuality(low=False, high=True)
        raise RuntimeError(f"Unknown backup quality: {backup_quality}")

    def get_backup_quality_for_newly_added_cameras(self) -> _BackupQuality:
        settings = self._get_backup_settings()
        return self._parse_backup_quality(settings['quality'])

    def get_camera_backup_quality(self, camera_id) -> _BackupQuality:
        camera = self.get_camera(camera_id)
        [backup_quality] = camera.backup_quality
        if backup_quality == 'CameraBackupDefault':
            return self.get_backup_quality_for_newly_added_cameras()
        return self._parse_backup_quality(backup_quality)

    def _list_recorded_periods_by_type(self, camera_id, period_type):
        raw_recorded_periods = self.http_get(
            f'rest/{self._version}/devices/{camera_id}/footage',
            params={'periodType': period_type})
        return [
            TimePeriod(
                start_ms=int(p['startTimeMs']),
                duration_ms=int(p['durationMs']) if int(p['durationMs']) != -1 else None,
                )
            for p in raw_recorded_periods
            ]

    def list_analytics_periods(self, camera_id):
        return self._list_recorded_periods_by_type(camera_id, 'analytics')

    def list_motion_periods(self, camera_id):
        return self._list_recorded_periods_by_type(camera_id, 'motion')

    def add_storage_encryption_key(self, password: str):
        self.http_post(f'rest/{self._version}/{self._site_term}/storageEncryption', {
            'password': password,
            'makeCurrent': True,
            })

    def list_db_backups(self) -> Collection[Mapping[str, str]]:
        return self.http_get(f'rest/{self._version}/servers/this/dbBackups')
