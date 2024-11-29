# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Any
from typing import Collection
from typing import Iterable
from typing import Mapping
from typing import Optional
from uuid import UUID

from mediaserver_api import LdapContinuousSyncMode
from mediaserver_api import UserGroupNotFound
from mediaserver_api._bookmarks import _BookmarkV3
from mediaserver_api._groups import GroupV3
from mediaserver_api._groups import Groups
from mediaserver_api._http_exceptions import NotFound
from mediaserver_api._ldap_settings import LdapSearchBase
from mediaserver_api._ldap_settings import _LdapSettingsV3
from mediaserver_api._mediaserver import _CreatedUser
from mediaserver_api._mediaserver import _format_uuid
from mediaserver_api._mediaserver_v2 import MediaserverApiV2
from mediaserver_api._users import UserV3

_logger = logging.getLogger(__name__)


class MediaserverApiV3(MediaserverApiV2):

    _version = 'v3'
    _keep_default_params = {}

    def list_users(self) -> Collection[UserV3]:
        users = self.http_get(f'rest/{self._version}/users', self._keep_default_params)
        return [UserV3(data) for data in users]

    def get_user(self, user_id):
        try:
            user_data = self.http_get(
                f'rest/{self._version}/users/{_format_uuid(user_id)}', self._keep_default_params)
        except NotFound:
            return None
        return UserV3(user_data)

    def add_local_user(
            self,
            name: str,
            password: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[UUID] = None,
            resources_access_rights: Optional[Mapping[UUID, Collection[str]]] = None,
            ) -> _CreatedUser:
        primary = self._make_local_user_primary_params(
            name,
            permissions=permissions,
            group_id=group_id,
            )
        auth_params = self._prepare_auth_params(name, password)
        arguments = {**primary, **auth_params}
        if resources_access_rights is not None:
            arguments['resourceAccessRights'] = {
                _format_uuid(resource_uuid): '|'.join(access_rights)
                for resource_uuid, access_rights in resources_access_rights.items()
                }
        user_id = self._add_user(arguments)
        return _CreatedUser(user_id, name, password)

    def add_multi_group_local_user(
            self,
            name: str,
            password: str,
            group_ids: Collection[UUID] = (),
            ) -> UUID:
        arguments = {
            'name': name,
            'groupIds': [_format_uuid(group_id) for group_id in group_ids],
            }
        auth_params = self._prepare_auth_params(name, password)
        arguments.update(auth_params)
        return self._add_user(arguments)

    def _make_local_user_primary_params(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[UUID] = None,
            ):
        return self._prepare_params({
            'name': name,
            'permissions': self._format_permissions(permissions),
            'groupIds': [_format_uuid(group_id)] if group_id is not None else None,
            })

    def add_local_admin(self, username, password):
        return self.add_local_user(username, password, group_id=Groups.POWER_USERS)

    def add_local_advanced_viewer(self, username, password):
        return self.add_local_user(username, password, group_id=Groups.ADVANCED_VIEWERS)

    def add_local_viewer(self, username, password):
        return self.add_local_user(username, password, group_id=Groups.VIEWERS)

    def add_local_live_viewer(self, username, password):
        return self.add_local_user(username, password, group_id=Groups.LIVE_VIEWERS)

    def _modify_user(self, user_id, primary):
        self.http_patch(f'rest/{self._version}/users/{_format_uuid(user_id)}', {**primary})

    def add_generated_user(
            self,
            idx: int,
            parent_id: Optional[str] = None,
            group_id: Optional[str] = None,
            ):
        generated_user_id = UUID(f'58e20000-0000-0000-0000-{idx:012d}')
        name = f'User_{idx}'
        password = name
        email = f'{name}@gmail.com'
        primary = {
            'id': str(generated_user_id),
            'name': name,
            'email': email,
            'password': password,
            }
        if group_id is not None:
            primary['groupIds'] = [group_id]
        user_id = self._add_user(primary)
        assert user_id == generated_user_id
        return _CreatedUser(generated_user_id, name, password)

    def set_user_access_rights(self, user_id, resource_ids, access_type='view'):
        final_resources = {}
        for resource_id, action in self.get_user(user_id).accessible_resources.items():
            final_resources[_format_uuid(resource_id)] = action
        new_resources = {_format_uuid(_id): access_type for _id in resource_ids}
        final_resources.update(new_resources)
        params = self._prepare_params({
            'resourceAccessRights': final_resources,
            })
        self.http_patch(f'rest/{self._version}/users/{_format_uuid(user_id)}', params)

    def list_user_groups(self) -> Collection[GroupV3]:
        raw = self.http_get(f'rest/{self._version}/userGroups', self._keep_default_params)
        return [GroupV3(group) for group in raw]

    def get_group_name(self, group_id):
        # Workaround for GUI tests. https://networkoptix.atlassian.net/browse/VMS-38693
        all_groups = self.http_get(f'rest/{self._version}/userGroups', self._keep_default_params)
        for group in all_groups:
            if group_id in group['id']:
                return group['name']
        raise RuntimeError(f'No group id {group_id} found on server')

    def add_user_group(
            self,
            name: str,
            permissions: Iterable[str],
            parent_group_ids: Optional[Iterable[UUID]] = None,
            resources_access_rights: Optional[Mapping[UUID, Collection[str]]] = None,
            ) -> UUID:
        group_data = {
            'name': name,
            'permissions': self._format_permissions(permissions),
            }
        if parent_group_ids is not None:
            group_data['parentGroupIds'] = [str(group_id) for group_id in parent_group_ids]
        if resources_access_rights is not None:
            normalized_access_rights = {
                _format_uuid(resource_uuid): self._format_permissions(access_rights)
                for resource_uuid, access_rights in resources_access_rights.items()
                }
            group_data['resourceAccessRights'] = normalized_access_rights
        response = self.http_post(f'rest/{self._version}/userGroups', group_data)
        return UUID(response['id'])

    def set_user_group(self, user_id, group_id: Groups):
        self._modify_user(user_id, {'groupIds': [str(group_id)]})

    def add_user_to_group(self, user_id, group_id: UUID):
        user_data = self.http_get(
            f'rest/{self._version}/users/{_format_uuid(user_id)}', self._keep_default_params)
        full_list_ids = [*user_data['groupIds'], str(group_id)]
        self._modify_user(user_id, {'groupIds': full_list_ids})

    def check_ldap_server(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]] = None,
            ):
        settings = _LdapSettingsV3(host, admin_dn, admin_password, search_base)
        self.http_post(f'rest/{self._version}/ldap/test', settings.as_dict())

    def set_ldap_settings(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]] = None,
            login_attribute: Optional[str] = None,
            group_object_class: Optional[str] = None,
            remove_records: bool = False,
            sync_mode: LdapContinuousSyncMode = LdapContinuousSyncMode.DISABLED,
            ):
        ldap_settings = _LdapSettingsV3(
            host=host,
            admin_dn=admin_dn,
            admin_password=admin_password,
            search_base=search_base,
            login_attribute=login_attribute,
            group_object_class=group_object_class,
            remove_records=remove_records,
            sync_mode=sync_mode,
            )
        self.http_patch(f'rest/{self._version}/ldap/settings', ldap_settings.as_dict())

    def set_ldap_password_expiration_period(self, period_sec: int):
        self.http_patch(
            f'rest/{self._version}/ldap/settings',
            {'passwordExpirationPeriodMs': period_sec * 1000})

    def sync_ldap_users(self, timeout: float = 30):
        self.http_post(f'rest/{self._version}/ldap/sync', {})
        started_at = time.monotonic()
        _logger.info("Waiting for LDAP synchronization to finish")
        while time.monotonic() - started_at <= timeout:
            if self._ldap_sync_finished():
                _logger.info("LDAP synchronization finished")
                return
            time.sleep(1)
        raise RuntimeError(f"LDAP synchronization didn't finish within {timeout} seconds")

    def _ldap_sync_finished(self) -> bool:
        response = self.http_get(f'rest/{self._version}/ldap/sync')
        return not response['isRunning']

    def connect_system_to_cloud(self, auth_key, system_id, user_email):
        self.http_post(f'rest/{self._version}/{self._site_term}/cloud/bind', {
            'authKey': auth_key,
            'systemId': system_id,
            'owner': user_email,
            })

    def _detach_from_cloud(self, password, current_password):
        self.http_post(f'rest/{self._version}/{self._site_term}/cloud/unbind', {'password': password})

    def add_dummy_smb_storage(self, index, parent_id=None):
        raise NotImplementedError("Unable to add storage using fake data in APIv3")

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
        bookmark = _BookmarkV3(response)
        return bookmark.id

    def list_bookmarks(self, camera_id):
        bookmarks_data = self.http_get(
            f'rest/{self._version}/devices/{_format_uuid(camera_id)}/bookmarks',
            self._keep_default_params)
        return [_BookmarkV3(data) for data in bookmarks_data]

    def get_bookmark(self, camera_id: UUID, bookmark_id: str):
        camera_id = _format_uuid(camera_id, strict=True)
        try:
            bookmark_data = self.http_get(
                f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark_id}',
                self._keep_default_params)
        except NotFound:
            return None
        return _BookmarkV3(bookmark_data)

    def set_bookmark_duration(self, bookmark: _BookmarkV3, duration_ms):
        # Need all values to update bookmark.
        camera_id = _format_uuid(bookmark.camera_id, strict=True)
        self.http_patch(f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark.id}', {
            'name': bookmark.name,
            'startTimeMs': str(bookmark.start_time_ms),
            'durationMs': str(duration_ms),
            })

    def remove_bookmark(self, bookmark: _BookmarkV3):
        self.http_delete(f'rest/{self._version}/devices/*/bookmarks/{bookmark.id}')

    def update_bookmark_description(self, camera_id: UUID, bookmark_id: str, new_description: str):
        camera_id = _format_uuid(camera_id, strict=True)
        self.http_patch(f'rest/{self._version}/devices/{camera_id}/bookmarks/{bookmark_id}', {
            'description': new_description,
            })

    def add_web_page(self, name, url):
        response = self.http_post(
            f'rest/{self._version}/webPages', {
                'name': name,
                'url': url,
                'proxyDomainAllowList': [''],
                })
        return UUID(response['id'])

    def get_ldap_settings(self) -> Mapping[str, Any]:
        data = self.http_get(f'rest/{self._version}/ldap/settings')
        return data

    def get_user_group(self, group_id: UUID | str) -> GroupV3:
        try:
            group_data = self.http_get(
                f'rest/{self._version}/userGroups/{_format_uuid(group_id)}', self._keep_default_params)
        except NotFound:
            raise UserGroupNotFound(f"Group {group_id} is not found")
        else:
            return GroupV3(group_data)


# See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/3459776513/Permissions+System#Resource-Access-Rights
class CameraPermissions:

    VIEW_LIVE = 'view'
    VIEW_ARCHIVE = 'viewArchive'
    USER_INPUT = 'userInput'
    EDIT = 'edit'
    AUDIO = 'audio'
    EXPORT_ARCHIVE = 'exportArchive'
    VIEW_BOOKMARKS = 'viewBookmarks'
    MANAGE_BOOKMARKS = 'manageBookmarks'
