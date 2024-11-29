# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from typing import Any
from typing import Mapping
from uuid import UUID

from mediaserver_api._base_resource import BaseResource

_logger = logging.getLogger(__name__)


class BaseUser(BaseResource, metaclass=ABCMeta):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self.is_enabled: bool = raw_data['isEnabled']
        self.is_ldap: bool = self._is_ldap(raw_data)
        self.is_cloud: bool = self._is_cloud(raw_data)
        permissions = set(raw_data['permissions'].split('|'))
        permissions.discard('none')
        self.permissions: Collection[str] = permissions
        self.email: str = raw_data.get('email', '')
        self.name: str = raw_data['name']
        self.full_name: str = raw_data['fullName']
        self.is_admin: bool = self._user_is_admin()

    @classmethod
    def _list_compared_attributes(cls):
        return [
            'email',
            'full_name',
            'is_admin',
            'is_cloud',
            'is_enabled',
            '_is_ldap',
            'name',
            'permissions',
            ]

    @abstractmethod
    def _user_is_admin(self):
        pass

    @staticmethod
    @abstractmethod
    def _is_ldap(raw_data):
        pass

    @staticmethod
    @abstractmethod
    def _is_cloud(raw_data):
        pass

    def __repr__(self):
        return f'<_User {self.name} {self.id}, parameters: {self.raw_data}>'


class UserV0(BaseUser):

    def __init__(self, raw_data):
        if 'groupIds' in raw_data:
            self.group_ids = [UUID(group_id) for group_id in raw_data['groupIds']]
        else:
            self.group_ids = []
        super().__init__(raw_data)
        try:
            self.group_id = UUID(raw_data['userRoleId'])
        except KeyError:
            _logger.debug("userRoleId attribute absent in VMS 6.0+")
        self._parent_id = UUID(raw_data['parentId'])
        self._url = raw_data['url']

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = ['_parent_id', '_url']
        return base_attributes + version_specific_attributes

    @staticmethod
    def _is_ldap(raw_data):
        if 'isLdap' in raw_data:
            return raw_data['isLdap']
        return raw_data['type'] == 'ldap'

    @staticmethod
    def _is_cloud(raw_data):
        if 'isCloud' in raw_data:
            return raw_data['isCloud']
        return raw_data['type'] == 'cloud'

    def _user_is_admin(self):
        if 'isAdmin' in self.raw_data:
            return self.raw_data['isAdmin']
        return UUID('00000000-0000-0000-0000-100000000000') in self.group_ids


class UserV1(BaseUser):

    def __init__(self, raw_data):
        super().__init__(raw_data)
        self.group_id = UUID(raw_data['userRoleId'])
        self._accessible_resources = [UUID(r) for r in raw_data.get('accessibleResources', [])]
        self.is_http_digest_enabled = raw_data['isHttpDigestEnabled']
        self._type = raw_data['type']

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = [
            'group_id', '_accessible_resources', 'is_http_digest_enabled', '_type']
        return base_attributes + version_specific_attributes

    @staticmethod
    def _is_ldap(raw_data):
        return raw_data['type'] == 'ldap'

    @staticmethod
    def _is_cloud(raw_data):
        return raw_data['type'] == 'cloud'

    def _user_is_admin(self):
        return self.raw_data['isOwner']


class UserV3(BaseUser):

    def __init__(self, raw_data):
        self.group_ids = set([UUID(group_id) for group_id in raw_data['groupIds']])
        super().__init__(raw_data)
        self._external_id = raw_data.get('externalId')  # For LDAP user this is DN
        self.synced = False if self._external_id is None else self._external_id['synced']
        self.is_http_digest_enabled = raw_data['isHttpDigestEnabled']
        resource_access_rights = raw_data['resourceAccessRights']
        self.accessible_resources = {
            UUID(resource_id): access_name
            for resource_id, access_name in resource_access_rights.items()
            if resource_id
            }
        self._type = raw_data['type']

    @classmethod
    def _list_compared_attributes(cls):
        base_attributes = super()._list_compared_attributes()
        version_specific_attributes = [
            '_external_id',
            'is_http_digest_enabled',
            'accessible_resources',
            '_type',
            'group_ids',
            ]
        return base_attributes + version_specific_attributes

    @staticmethod
    def _is_ldap(raw_data):
        return raw_data['type'] == 'ldap'

    @staticmethod
    def _is_cloud(raw_data):
        return raw_data['type'] == 'cloud'

    def _user_is_admin(self):
        return UUID('00000000-0000-0000-0000-100000000000') in self.group_ids

    def is_group_member(self, group_id: UUID):
        return group_id in self.group_ids

    def get_integration_request_data(self) -> Mapping[str, Any] | None:
        return self.raw_data['parameters'].get('integrationRequestData')


class Permissions:
    NO_GLOBAL = "NoGlobalPermissions"
    ADMIN = "GlobalAdminPermission"
    ACCESS_ALL_MEDIA = "GlobalAccessAllMediaPermission"
    VIEW_ARCHIVE = "GlobalViewArchivePermission"
    EXPORT = "GlobalExportPermission"
    VIEW_BOOKMARKS = "GlobalViewBookmarksPermission"
    MANAGE_BOOKMARKS = "GlobalManageBookmarksPermission"
    USER_INPUT = "GlobalUserInputPermission"
    EDIT_CAMERAS = "GlobalEditCamerasPermission"
    CONTROL_VIDEOWALL = "GlobalControlVideoWallPermission"
    VIEW_LOGS = "GlobalViewLogsPermission"
    CUSTOM_USER = "GlobalCustomUserPermission"

    # Commonly known user groups.
    VIEWER_PRESET = (
        ACCESS_ALL_MEDIA,
        VIEW_ARCHIVE,
        EXPORT,
        VIEW_BOOKMARKS,
        )
    ADVANCED_VIEWER_PRESET = (
        *VIEWER_PRESET,
        MANAGE_BOOKMARKS,
        USER_INPUT,
        VIEW_LOGS,
        )
    NONADMIN_FULL_PRESET = (
        *ADVANCED_VIEWER_PRESET,
        EDIT_CAMERAS,
        CONTROL_VIDEOWALL,
        CUSTOM_USER,
        )


class PermissionsV3:
    VIEW_LOGS = "viewLogs"
    GENERATE_EVENTS = "generateEvents"
    VIEW_METRICS = "viewMetrics"


# System administrator (admin user) has hard-coded GUID.
# You can check it by using ec2/getUsers API call.
SYSTEM_ADMIN_USER_ID = '{99cbc715-539b-4bfe-856f-799b45b69b1e}'


class ResourceGroups:
    ALL_DEVICES = UUID('00000000-0000-0000-0000-200000000001')
