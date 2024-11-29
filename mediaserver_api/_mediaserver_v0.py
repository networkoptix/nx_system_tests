# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import json
import logging
import time
from collections.abc import Collection
from collections.abc import Mapping
from typing import Any
from typing import NamedTuple
from typing import Optional
from typing import Union
from uuid import UUID
from uuid import uuid3

from mediaserver_api._bookmarks import _BookmarkV0
from mediaserver_api._cameras import _CameraV0
from mediaserver_api._groups import UserGroup
from mediaserver_api._http_auth import user_digest
from mediaserver_api._http_exceptions import MediaserverApiHttpError
from mediaserver_api._layouts import Layout
from mediaserver_api._mediaserver import MediaserverApi
from mediaserver_api._mediaserver import Videowall
from mediaserver_api._mediaserver import _format_uuid
from mediaserver_api._merge_exceptions import CloudSystemsHaveDifferentOwners
from mediaserver_api._merge_exceptions import DependentSystemBoundToCloud
from mediaserver_api._merge_exceptions import IncompatibleCloud
from mediaserver_api._merge_exceptions import MergeDuplicateMediaserverFound
from mediaserver_api._servers import ServerV0
from mediaserver_api._storage import Storage
from mediaserver_api._storage import WrongPathError
from mediaserver_api._users import UserV0
from mediaserver_api._web_pages import WebPage

_logger = logging.getLogger(__name__)


class AuditTrailEventTypesV0(NamedTuple):
    CAMERA_INSERT = 'AR_CameraInsert'
    CAMERA_REMOVE = 'AR_CameraRemove'
    CAMERA_UPDATE = 'AR_CameraUpdate'
    DATABASE_RESTORE = 'AR_DatabaseRestore'
    EMAIL_SETTINGS = 'AR_EmailSettings'
    EVENT_RULE_REMOVE = 'AR_BEventRemove'
    EVENT_RULE_RESET = 'AR_BEventReset'
    EVENT_RULE_UPDATE = 'AR_BEventUpdate'
    EXPORT_VIDEO = 'AR_ExportVideo'
    LOGIN = 'AR_Login'
    NOT_DEFINED = 'AR_NotDefined'
    SERVER_REMOVE = 'AR_ServerRemove'
    SERVER_UPDATE = 'AR_ServerUpdate'
    SETTINGS_CHANGE = 'AR_SettingsChange'
    STORAGE_INSERT = 'AR_StorageInsert'
    STORAGE_REMOVE = 'AR_StorageRemove'
    STORAGE_UPDATE = 'AR_StorageUpdate'
    SITES_MERGE = 'AR_SystemmMerge'  # It's a typo in C++ source  # noqa SpellCheckingInspection
    SITE_NAME_CHANGED = 'AR_SystemNameChanged'
    UNAUTHORIZED_LOGIN = 'AR_UnauthorizedLogin'
    UPDATE_INSTALL = 'AR_UpdateInstall'
    USER_REMOVE = 'AR_UserRemove'
    USER_UPDATE = 'AR_UserUpdate'
    VIEW_ARCHIVE = 'AR_ViewArchive'
    VIEW_LIVE = 'AR_ViewLive'


class MediaserverApiV0(MediaserverApi):

    _preferred_auth_type = 'digest'
    _version = 'v0'
    _site_term = 'system'
    audit_trail_events = AuditTrailEventTypesV0

    def add_web_page(self, name, url):
        response = self.http_post('ec2/saveWebPage', {'name': name, 'url': url})
        return UUID(response['id'])

    def list_web_pages(self):
        return [WebPage(data) for data in self.http_get('ec2/getWebPages')]

    def get_web_page(self, page_id):
        web_pages = self.http_get('ec2/getWebPages', {'id': _format_uuid(page_id, strict=True)})
        if not web_pages:
            return None
        [web_page_data] = web_pages
        return WebPage(web_page_data)

    def modify_web_page(self, page_id, name=None, url=None):
        primary = self._prepare_params(
            {'id': _format_uuid(page_id, strict=True), 'name': name, 'url': url})
        self.http_post('ec2/saveWebPage', primary)

    def remove_web_page(self, page_id):
        self.http_post('ec2/removeWebPage', {'id': _format_uuid(page_id, strict=True)})

    def add_bookmark(self, camera_id, name, start_time_ms=0, duration_ms=60000, description=None):
        uuid_namespace = UUID('80044a44-add0-0000-0000-000000000000')
        bookmark_id = uuid3(uuid_namespace, str(camera_id) + name)
        self.http_get('ec2/bookmarks/add', {
            'name': name,
            'cameraId': _format_uuid(camera_id, strict=True),
            'guid': str(bookmark_id),
            'startTime': start_time_ms,
            'duration': duration_ms,
            })
        return bookmark_id

    def list_bookmarks(self, camera_id):
        bookmarks_data = self.http_get(
            'ec2/bookmarks', params={'cameraId': _format_uuid(camera_id)})
        return [_BookmarkV0(data) for data in bookmarks_data]

    def get_bookmark(self, camera_id, bookmark_id):
        # Mediaserver does not support direct http call with guid to get single bookmark
        bookmarks = self.list_bookmarks(camera_id)
        for b in bookmarks:
            if b.id == bookmark_id:
                return b
        return None

    def set_bookmark_duration(self, bookmark: _BookmarkV0, duration_ms):
        # Need all values to update bookmark.
        self.http_get('ec2/bookmarks/update', {
            'name': bookmark.name,
            'cameraId': _format_uuid(bookmark.camera_id, strict=True),
            'guid': _format_uuid(bookmark.id, strict=True),
            'startTime': bookmark.start_time_ms,
            'duration': duration_ms,
            })

    def remove_bookmark(self, bookmark: _BookmarkV0):
        self.http_get(
            'ec2/bookmarks/delete', {'guid': _format_uuid(bookmark.id, strict=True)})

    def update_bookmark_description(self, camera_id, bookmark_id, new_description):
        raise NotImplementedError()

    def _get_servers_timestamp(self):
        return [time_info['vmsTime'] for time_info in self.http_get('/ec2/getTimeOfServers')]

    def _add_layout(self, primary):
        response = self.http_post('ec2/saveLayout', primary)
        return UUID(response['id'])

    def add_layout(self, name, type_id=None):
        if type_id is None:
            type_id = self._layout_type_id
        return self._add_layout({'name': name, 'typeId': _format_uuid(type_id, strict=True)})

    def add_layout_with_resource(self, name, resource_id):
        return self._add_layout({
            'name': name,
            'items': [{
                'resourceId': str(resource_id),
                'flags': 1, 'left': 0, 'top': 0, 'right': 1,
                'bottom': 1,
                }],
            'cellAspectRatio': 1,
            'fixedWidth': 1,
            'fixedHeight': 1,
            })

    def add_shared_layout_with_resource(self, name: str, resource_id: UUID) -> UUID:
        return self._add_layout({
            'name': name,
            'items': [{
                'resourceId': str(resource_id),
                'flags': 1, 'left': 0, 'top': 0, 'right': 1,
                'bottom': 1,
                }],
            'cellAspectRatio': 1,
            'fixedWidth': 1,
            'fixedHeight': 1,
            # If parentId of layout is specified, this layout is only available to the user
            # whose ID is specified in parentId. If the parentId value is not passed in the request,
            # it will be automatically set with the request's user id. To make the layout shared,
            # the parentId value must be passed as a nil UUID.
            'parentId': str(UUID(int=0)),
            })

    def add_generated_layout(self, primary):
        return self._add_layout(primary)

    def list_layouts(self):
        response = self.http_get('ec2/getLayouts')
        return [Layout(layout_data) for layout_data in response]

    def get_layout(self, layout_id):
        response = self.http_get('ec2/getLayouts', {'id': _format_uuid(layout_id, strict=True)})
        if not response:
            return None
        [layout_data] = response
        return Layout(layout_data)

    def remove_layout(self, layout_id):
        self.remove_resource(layout_id)

    def _add_camera(self, primary):
        response = self.http_post('ec2/saveCamera', primary)
        return UUID(response['id'])

    def add_generated_camera(self, primary, attributes=None, params=None):
        self._add_camera(primary)
        if attributes is not None:
            self._save_camera_attributes(primary['id'], attributes)
        if params is not None:
            self.set_camera_resource_params(primary['id'], params)

    def list_cameras(self):
        cameras = self.http_get('ec2/getCamerasEx', timeout=60)
        return [_CameraV0(camera_data) for camera_data in cameras]

    def get_camera(self, camera_id, is_uuid=True, validate_logical_id=True):
        camera_id = self._format_camera_id(camera_id, is_uuid, validate_logical_id)
        data = self.http_get('ec2/getCamerasEx', {'id': camera_id})
        if not data:
            return None
        [camera_data] = data
        return _CameraV0(camera_data)

    def _modify_camera(self, camera_id, primary):
        self.http_post('ec2/saveCamera', {**primary, 'id': _format_uuid(camera_id)})

    def _list_recorded_periods(self, camera_ids, periods_type=None, detail_level_ms=None):
        camera_params = [('cameraId', str(i)) for i in camera_ids]
        if periods_type is not None:
            camera_params = [('periodsType', periods_type), *camera_params]
        if detail_level_ms is not None:
            camera_params = [('detail', str(detail_level_ms)), *camera_params]
        reply = self.http_get(
            'ec2/recordedTimePeriods',
            params=[('groupBy', 'cameraId'), *camera_params])
        return {UUID(g['guid']): g['periods'] for g in reply}

    def _save_camera_attributes(self, camera_id, attributes):
        self.http_post(
            'ec2/saveCameraUserAttributes',
            {**attributes, 'cameraId': _format_uuid(camera_id)})

    def _save_camera_attributes_list(self, camera_ids, new_attributes):
        # If these attributes are not specified, their values are reset to defaults
        attributes_to_save = [
            'audioEnabled',
            'backupType',
            'cameraName',
            'controlEnabled',
            'dewarpingParams',
            'disableDualStreaming',
            'failoverPriority',
            'licenseUsed',
            'logicalId',
            'maxArchiveDays',  # vms_5.0 and earlier
            'minArchiveDays',  # vms_5.0 and earlier
            'maxArchivePeriodS',  # vms_5.0_patch
            'minArchivePeriodS',  # vms_5.0_patch
            'motionMask',
            'motionType',
            'preferredServerId',
            'recordAfterMotionSec',
            'recordBeforeMotionSec',
            'scheduleEnabled',
            'scheduleTasks',
            ]
        attributes_list = []
        all_cameras = self.http_get('ec2/getCamerasEx')
        camera_uuids = []
        for camera_id in camera_ids:
            if isinstance(camera_id, UUID):
                camera_uuids.append(camera_id)
                continue
            try:
                uuid_id = UUID(camera_id)
            except ValueError:  # not UUID
                uuid_id = None
                for camera in all_cameras:
                    if not (
                            camera.get('physicalId') == camera_id
                            or camera.get('logicalId') == camera_id):
                        continue
                    uuid_id = UUID(camera['id'])
                    break
                if uuid_id is None:
                    raise RuntimeError(f"No camera with ID {camera_id} was found")
            camera_uuids.append(uuid_id)
        for camera in all_cameras:
            camera_id = UUID(camera['id'])
            if camera_id not in camera_uuids:
                continue
            current_attributes = {k: v for k, v in camera.items() if k in attributes_to_save}
            attributes_list.append(
                {**current_attributes, **new_attributes, 'cameraId': _format_uuid(camera_id)})
        self.http_post('ec2/saveCameraUserAttributesList', attributes_list)

    def rename_camera(self, camera_id, new_name):
        # Non-empty 'cameraName' value overrides 'name' value. If 'cameraName' was set via some
        # API request or desktop Client, altering 'name' won't take any effect
        self._save_camera_attributes(camera_id, {'cameraName': new_name})

    def _set_camera_streams(self, camera_id: UUID, primary_stream_url: str, secondary_stream_url: str):
        # Endpoint call does not append url to current parameters, it rewrites current parameters.
        # For example, to append secondary url to current params pass both urls in POST params.
        urls = json.dumps(self._make_camera_stream_urls(camera_id))
        self.set_camera_resource_params(camera_id, {'streamUrls': urls})

    def remove_camera(self, camera_id):
        self.remove_resource(camera_id)

    def _start_manual_cameras_search(self, camera_url, credentials):
        response = self.http_get('api/manualCamera/search', {'url': camera_url, **credentials})
        return UUID(hex=response['processUuid'])

    def _get_manual_cameras_search_state(self, search_id):
        response = self.http_get('api/manualCamera/status', {'uuid': str(search_id)})
        manual_cameras = {}
        for data in response['cameras']:
            physical_id = data['physicalId'] if 'physicalId' in data else data['uniqueId']
            manual_cameras[physical_id] = data
        status = response['status']
        return manual_cameras, status

    def _add_manual_cameras_to_db(self, searcher_camera_list, credentials):
        self.http_post('api/manualCamera/add', {'cameras': searcher_camera_list, **credentials})

    def add_manual_camera_sync(
            self,
            camera_url: str,
            user: Optional[str] = None,
            password: Optional[str] = None,
            ):
        gen = self._add_camera_manually(camera_url, user=user, password=password)
        while True:
            try:
                next(gen)
            except StopIteration as exc:
                return exc.value
            time.sleep(1)

    def _add_mediaserver(self, data):
        if 'osInfo' in data:
            prepared_data = {**data, 'osInfo': json.dumps(data['osInfo'])}
        else:
            prepared_data = data
        response = self.http_post('ec2/saveMediaServer', prepared_data)
        return UUID(response['id'])

    def add_dummy_mediaserver(self, index):
        data = self._make_dummy_mediaserver_data(index)
        return self._add_mediaserver(data)

    def add_generated_mediaserver(self, primary, attributes=None):
        server_id = self._add_mediaserver(primary)
        if attributes is not None:
            self._save_server_attributes(server_id, attributes)

    def _get_timestamp_ms(self) -> int:
        return self.http_get('api/gettime')['utcTime']  # noqa SpellCheckingInspection

    def request_restart(self):
        self.http_post('api/restart', {})

    def list_servers(self):
        return [ServerV0(data) for data in self.http_get('ec2/getMediaServersEx')]

    def get_server(self, server_id):
        servers = self.http_get('ec2/getMediaServersEx', {'id': _format_uuid(server_id)})
        if not servers:
            return None
        [server] = servers
        return ServerV0(server)

    def _save_server_attributes(self, server_id, attributes):
        self.http_post(
            'ec2/saveMediaServerUserAttributes',
            {**attributes, 'serverId': _format_uuid(server_id)})

    def rename_server(self, new_server_name, server_id=None):
        if server_id is None:
            server_id = self.get_server_id()
        self._save_server_attributes(server_id, {'serverName': new_server_name})

    def remove_server(self, server_id):
        self.remove_resource(server_id)

    def _get_server_info(self):
        return self.http_get('api/moduleInformationAuthenticated')

    class MediaserverInfo(MediaserverApi.MediaserverInfo):

        def _parse_raw_data(self):
            return {
                'server_id': UUID(self._raw_data['id']),
                'local_site_id': UUID(self._raw_data.get('localSystemId', '{00000000-0000-0000-0000-000000000000}')),
                'server_name': self._raw_data['name'],
                'site_name': self._raw_data['systemName'],
                'customization': self._raw_data['customization'],
                }

    def get_module_info(self, target_server: Optional[UUID] = None):
        headers = {}
        if target_server is not None:
            headers['X-server-guid'] = _format_uuid(target_server)
        reply = self.http_get('api/moduleInformation', headers=headers)
        reply.pop('synchronizedTimeMs', None)
        return reply

    def _get_storage_info(self, path_or_url):
        return self.http_get(
            'api/storageStatus', {'path': path_or_url},
            timeout=40,  # Takes 20 sec on Windows if password is incorrect.
            )

    def _add_storage(self, primary):
        response = self.http_post('ec2/saveStorage', primary)
        return UUID(response['id'])

    def add_storage(self, path_or_url, storage_type, is_backup=False):
        info = self._get_storage_info(path_or_url)
        if info['status'] == 'InitFailed_WrongAuth':
            raise PermissionError("Wrong credentials: {}".format(path_or_url))
        if info['status'] == 'InitFailed_WrongPath':
            raise WrongPathError("Wrong path: {}".format(path_or_url))
        if info['status'].lower() != 'ok':
            raise RuntimeError("Bad storage status: {}: {}".format(
                info['status'], path_or_url))
        if info['storage']['storageType'].lower() != storage_type.lower():
            raise RuntimeError("Wrong storage type: {!r} != {!r}: {}".format(
                info['storage']['storageType'], type, path_or_url))
        reserved_space = info['storage']['reservedSpace']
        return self._add_storage(dict(
            storageType=info['storage']['storageType'],
            url=path_or_url,
            parentId=str(self.get_server_id()),
            isBackup=is_backup,
            usedForWriting=True,
            spaceLimit=reserved_space,
            name=path_or_url.split('/')[-1],
            ))

    def add_dummy_smb_storage(self, index, parent_id=None):
        parent_id = parent_id if parent_id is not None else self.get_server_id()
        return self._add_storage({
            'storageType': 'smb',
            'url': f'smb://10.255.255.123/FakePath_{index}',
            'parentId': _format_uuid(parent_id),
            'usedForWriting': True,
            'name': f'FakePath_{index}',
            })

    def _list_storage_objects(self):
        storage_data = self.http_get('api/storageSpace')['storages']
        return [Storage(s) for s in storage_data]

    def list_all_storages(self):
        current_server_id = self.get_server_id()
        storages = []
        for server in self.list_servers():
            if server.status == 'Offline':
                continue
            if server.id == current_server_id:
                kwargs = {}
            else:
                # The api/storageSpace endpoint returns storages owned only by the current server.
                # To get storage from another server, its ID must be passed
                # in the X-server-guid header.
                kwargs = {'headers': {'X-server-guid': _format_uuid(server.id)}}
            for data in self.http_get('api/storageSpace', **kwargs)['storages']:
                storages.append(Storage(data))
        return storages

    def get_storage(self, storage_id: UUID):
        storages = self._list_storage_objects()
        for storage in storages:
            if storage.id == storage_id:
                return storage
        return None

    def get_metadata_storage_id(self):
        server_id = self.get_server_id()
        storage_params = self.list_resource_params(server_id)
        for param in storage_params:
            if param['name'] == 'metadataStorageId':
                return UUID(param['value'])
        _logger.info("metadataStorageId param is not found for Server %s", server_id)
        return None

    def _modify_storage(self, storage_id, primary):
        self.http_post('ec2/saveStorage', {**primary, 'id': _format_uuid(storage_id)})

    def allocate_storage_for_analytics(self, storage_id):
        server_id = self.get_server_id()
        storage_id = _format_uuid(storage_id)
        self._set_resource_params(server_id, {'metadataStorageId': storage_id})

    def remove_storage(self, storage_id):
        if not isinstance(storage_id, UUID):
            storage_id = UUID(storage_id)  # Check for correctness.
        _logger.debug("Remove storage: %s", storage_id)
        response = self.http_post('ec2/removeStorage', {'id': _format_uuid(storage_id)})
        returned_id = UUID(response['id'])
        if returned_id != storage_id:
            raise RuntimeError(
                f"ec2/removeStorage returned {returned_id}, which differs from sent {storage_id}")

    def _add_user(self, primary):
        response = self.http_post('ec2/saveUser', primary)
        return UUID(response['id'])

    def _prepare_auth_params(self, name, password):
        # Mediaserver allows to pass password as plaintext string without hashing it into auth
        # params. But mediaserver client always hashes password, so we need to test requests with
        # auth params.
        response = self.http_get('api/getNonce')
        realm = response['realm']
        auth_digest = user_digest(realm, name, password)
        salt = b'd0d7971d'  # Predefined `salt` (non-random) is used for reproducibility
        md5_digest = hashlib.md5(salt + password.encode('ascii')).hexdigest()
        auth_password_hash = "md5$%s$%s" % (salt.decode('ascii'), md5_digest)
        return {
            "digest": auth_digest,
            "realm": realm,
            "hash": auth_password_hash,
            }

    def list_users(self) -> Collection[UserV0]:
        return [UserV0(data) for data in self.http_get('ec2/getUsers')]

    def get_user(self, user_id):
        users = self.http_get('ec2/getUsers', {'id': _format_uuid(user_id)})
        if not users:
            return None
        [user] = users
        return UserV0(user)

    def _modify_user(self, user_id, primary):
        self.http_post('ec2/saveUser', {**primary, 'id': _format_uuid(user_id)})

    def set_user_password(self, user_id, password):
        user = self.get_user(user_id)
        if user is None:
            raise RuntimeError("Cannot set password for user that does not exist")
        auth_params = self._prepare_auth_params(user.name, password)
        self._modify_user(user_id, auth_params)

    def set_user_credentials(self, user_id, name, password):
        auth_params = self._prepare_auth_params(name, password)
        self._modify_user(user_id, {'name': name, **auth_params})

    def remove_user(self, user_id):
        self.http_post('ec2/removeUser', dict(id=_format_uuid(user_id)))

    def set_user_access_rights(self, user_id, resource_ids, access_type='view'):
        params = {'userId': _format_uuid(user_id)}
        if self.server_older_than('vms_6.0'):
            params['resourceIds'] = [_format_uuid(_id) for _id in resource_ids]
        else:
            params['resourceRights'] = {_format_uuid(_id): access_type for _id in resource_ids}
        self.http_post('ec2/setAccessRights', params)

    def _add_user_group(self, primary):
        response = self.http_post('ec2/saveUserRole', primary)
        return UUID(response['id'])

    def get_user_group(self, group_id):
        user_groups = self.http_get('ec2/getUserRoles', {'id': _format_uuid(group_id)})
        if not user_groups:
            raise UserGroupNotFound(f"Group {group_id} is not found")
        [user_group] = user_groups
        return UserGroup(user_group)

    def _modify_user_group(self, group_id, primary):
        self.http_post('ec2/saveUserRole', {**primary, 'id': _format_uuid(group_id)})

    def remove_user_group(self, group_id):
        self.http_post('ec2/removeUserRole', dict(id=_format_uuid(group_id)))

    def set_group_access_rights(self, group_id, resource_ids):
        params = self._prepare_params({
            'userId': _format_uuid(group_id),
            'resourceIds': [_format_uuid(_id) for _id in resource_ids],
            })
        self.http_post('ec2/setAccessRights', params)

    def _get_version(self):
        return self.http_get('/api/moduleInformation')['version']

    def _make_local_setup_request(self, system_name, password, system_settings, settings_preset):
        data = {
            'systemName': system_name,
            'password': password,
            'systemSettings': system_settings,
            }
        if settings_preset is not None:
            data['settingsPreset'] = settings_preset
        self.http_post('api/setupLocalSystem', data)

    def _detach_from_system(self):
        self.http_post('api/detachFromSystem', {'currentPassword': self._password})

    @property
    def _version_specific_system_settings(self):
        return {
            # After VMS-27998, some endpoints from this version of the API, marked as insecure
            # and deprecated, are disabled by default. It is intended to use their alternatives
            # from a newer version of the API.
            # Enable them to be able to test this version of the API.
            'insecureDeprecatedApiEnabled': 'true',
            }

    def _make_cloud_setup_request(
            self, system_name, cloud_system_id, auth_key, account_name, system_settings):
        data = {
            'systemName': system_name,
            'cloudSystemID': cloud_system_id,
            'cloudAuthKey': auth_key,
            'cloudAccountName': account_name,
            'systemSettings': system_settings,
            }
        return self.http_post('api/setupCloudSystem', data, timeout=300)

    def connect_system_to_cloud(self, auth_key, system_id, user_email):
        self.http_post('/api/saveCloudSystemCredentials', {
            'cloudAuthKey': auth_key,
            'cloudSystemID': system_id,
            'cloudAccountName': user_email,
            })

    def _detach_from_cloud(self, password, current_password):
        self.http_post(
            'api/detachFromCloud',
            {
                'password': password,
                'currentPassword': current_password,
                })

    def get_system_settings(self):
        return self.http_get('/api/systemSettings', timeout=40)['settings']

    def get_site_name(self) -> str:
        return self.get_system_settings()['systemName']

    def get_local_system_id(self):
        return UUID(self.http_get('api/ping')['localSystemId'])

    def merge_in_progress(self, timeout_sec):
        status = self.http_get('ec2/mergeStatus', timeout=timeout_sec)
        return status['mergeInProgress']

    def get_auth_data(self) -> tuple[str, str]:
        return self.auth_key('GET'), self.auth_key('POST')

    def _request_merge(
            self,
            remote_url: str,
            remote_auth: tuple[str, str],
            take_remote_settings=False,
            merge_one_server=False):
        [remote_get_key, remote_post_key] = remote_auth
        try:
            return self.http_post('api/mergeSystems', {
                'url': remote_url,
                'getKey': remote_get_key,
                'postKey': remote_post_key,
                'takeRemoteSettings': take_remote_settings,
                'mergeOneServer': merge_one_server,
                })
        except MediaserverApiHttpError as e:
            if e.vms_error_string == 'CLOUD_SYSTEMS_HAVE_DIFFERENT_OWNERS':
                raise CloudSystemsHaveDifferentOwners(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            if e.vms_error_string == 'DEPENDENT_SYSTEM_BOUND_TO_CLOUD':
                raise DependentSystemBoundToCloud(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            if e.vms_error_string == 'INCOMPATIBLE_INTERNAL':
                raise IncompatibleCloud(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            if e.vms_error_string == 'DUPLICATE_MEDIASERVER_FOUND':
                raise MergeDuplicateMediaserverFound(
                    self, remote_url, e.vms_error_code, e.vms_error_string)
            raise

    def _add_videowall(self, primary):
        response = self.http_post('ec2/saveVideowall', primary)
        return UUID(response['id'])

    def remove_videowall(self, videowall_id):
        self.http_post('ec2/removeVideowall', {'id': _format_uuid(videowall_id)})

    def list_videowalls(self):
        return [Videowall(data) for data in self.http_get('ec2/getVideowalls')]

    def _request_with_required_authentication(self):
        self.get_server_info()

    def change_cameras_group_name(self, camera_ids, new_group_name):
        self._save_camera_attributes_list(camera_ids, {'userDefinedGroupName': new_group_name})

    def add_license(self, license_key: str, license_block: str):
        self.http_post('ec2/addLicenses', [{'key': license_key, 'licenseBlock': license_block}])

    def _activate_license(self, license_key: str):
        self.http_get('api/activateLicense', {'key': license_key})

    def remove_license(self, license_key: str):
        self.http_post('ec2/removeLicense', {'key': license_key})

    def _list_licenses(self):
        return self.http_get('ec2/getLicenses')

    def _get_server_flags(self):
        return self.http_get('api/moduleInformation')['serverFlags']

    def _dump_database(self):
        database = self.http_get('ec2/dumpDatabase')['data']
        return database.encode('ascii')

    def _restore_database(self, database):
        base64_backup_data_str = database.decode('ascii')
        self.http_post('ec2/restoreDatabase', {'data': base64_backup_data_str})

    def wait_for_backup_finish(self):
        timeout_sec = 60
        started_at = time.monotonic()
        while True:
            backup_response = self.http_get('api/backupControl')
            backup_state = backup_response['state']
            backup_up_to_ms = int(backup_response['backupTimeMs'])
            if backup_state == 'BackupState_None' and backup_up_to_ms != 0:
                return
            if time.monotonic() - started_at > timeout_sec:
                raise TimeoutError("Archive didn't back up after timeout")
            time.sleep(2)

    def _enable_failover(self, max_cameras):
        attributes = {'maxCameras': max_cameras, 'allowAutoRedundancy': True}
        self._save_server_attributes(self.get_server_id(), attributes)

    def _set_backup_quality_for_newly_added_cameras(self, low: bool, high: bool):
        # 1 (high), 2 (low), 3 (both).
        quality = high + (low << 1)
        self.set_system_settings({'backupQualities': quality})

    def enable_backup_for_newly_added_cameras(self):
        self.set_system_settings({'backupNewCamerasByDefault': True})

    def disable_backup_for_newly_added_cameras(self):
        self.set_system_settings({'backupNewCamerasByDefault': False})

    def _restore_state(self):
        self.http_post('api/restoreState', {'currentPassword': self._password})

    def merge_is_finished(
            self,
            merge_responses,
            merge_timeout_sec,
            ):
        timeout_sec = max(20., merge_timeout_sec / 10)
        merge_history = self.get_merge_history()
        # TODO: Check the merge history in APIv1 after implementing the endpoint: VMS-23031
        # Currently, the result of a merge history request from the old API endpoint
        # cannot be compared to the result of a merge request from the new API
        for response in merge_responses:
            if response not in merge_history:
                _logger.info("Response %s not in %s merge history", response, self)
                return False
        if self.merge_in_progress(timeout_sec=timeout_sec):
            _logger.info("Merge is in progress on %s", self)
            return False
        return True

    def backup_is_enabled_for_newly_added_cameras(self):
        raise NotImplementedError()

    def get_backup_quality_for_newly_added_cameras(self):
        raise NotImplementedError()

    def get_camera_backup_quality(self, camera_id):
        raise NotImplementedError()

    def list_analytics_periods(self, camera_id):
        raise NotImplementedError()

    def list_motion_periods(self, camera_id):
        raise NotImplementedError()

    def add_storage_encryption_key(self, password: str):
        raise NotImplementedError()

    def list_db_backups(self):
        raise NotImplementedError("The endpoint does not exist in APIv0")

    def _update_info_match(self, update_info):
        return self._update_info() == update_info

    def _start_update(self, update_info):
        self.http_post('ec2/startUpdate', update_info)

    def _update_info(self):
        update_info = self.http_get('ec2/updateInformation')
        # Version 5.0.0 doesn't include 'customClientVariant' field in the update info.
        if update_info.get('packages', []):
            if 'customClientVariant' not in update_info['packages'][0]:
                update_info['packages'][0]['customClientVariant'] = ''
        return update_info

    def _update_status(self):
        return self.http_get('ec2/updateStatus')

    def cancel_update(self):
        self.http_post('ec2/cancelUpdate', {})

    @staticmethod
    def _prepare_update_info(update_info):
        return {
            'description': '',
            'participants': [],
            'lastInstallationRequestTime': '-1',
            'version': update_info['version'],
            'cloudHost': update_info['cloud_host'],
            'eulaLink': 'http://new.eula.com/eulaText',
            'eulaVersion': 1,
            'eula': '',
            'releaseNotesUrl': 'http://www.networkoptix.com/all-nx-witness-release-notes',
            'releaseDeliveryDays': 0,
            'packages': [
                MediaserverApiV0._prepare_package_info(p)
                for p in update_info['packages']
                ],
            'releaseDate': '0',
            'url': '',
            }

    @staticmethod
    def _prepare_package_info(package_info):
        return {
            'component': 'server',
            'customClientVariant': '',
            'platform': package_info['platform'],
            'variants': [],
            'file': package_info['file'],
            'url': package_info['url'],
            'size': str(package_info['size']),
            'md5': package_info['md5'],
            'signature': package_info['signature'],
            }

    def create_integration_request(
            self,
            integration_manifest: Mapping[str, Any],
            engine_manifest: Mapping[str, Any],
            pin_code: str,
            ):
        raise NotImplementedError("Integration request is only available in API v4+")

    def approve_integration_request(self, request_id: UUID):
        raise NotImplementedError("Integration request is only available in API v4+")

    def _best_shot_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        # The image is in JPG format.
        return self._http_download(
            path='/ec2/analyticsTrackBestShot',
            params={
                'cameraId': camera_id,
                'objectTrackId': track_id,
                },
            )

    def _title_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        # The image is in JPG format.
        return self._http_download(
            path='/ec2/analyticsTrackTitle',
            params={
                'cameraId': camera_id,
                'objectTrackId': track_id,
                },
            )

    def execute_analytics_action(
            self,
            engine_id: UUID,
            action_id: str,
            object_track_id: UUID,
            camera_id: UUID,
            timestamp: int,
            params: Optional[Mapping] = None,
            ) -> Mapping[str, Union[str, bool]]:
        data = {
            'engineId': _format_uuid(engine_id),
            'actionId': action_id,
            'objectTrackId': _format_uuid(object_track_id),
            'deviceId': _format_uuid(camera_id),
            'timestampUs': str(timestamp * 1000),
            }
        if params is not None:
            data = {**data, 'params': params}
        return self.http_post('api/executeAnalyticsAction', data)

    def _get_raw_analytics_engines(self):
        return self.http_get('/ec2/getAnalyticsEngines')

    def get_ldap_settings(self) -> Mapping[str, Any]:
        raise NotImplementedError("Not implemented yet")


class InsecureMediaserverApiV0(MediaserverApiV0):
    _basic_and_digest_auth_required = True


class UserGroupNotFound(Exception):
    pass
