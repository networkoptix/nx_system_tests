# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections.abc import Collection
from collections.abc import Mapping
from typing import Any
from uuid import UUID


class ChannelPartnerOrganizationData:

    def __init__(self, raw: Mapping[str, Any]):
        self._raw = raw
        self._id = UUID(self._raw['id'])

    def __repr__(self):
        return f"<{self.__class__.__name__}, ID: {self._id}>"

    def get_channel_partner_id(self) -> UUID:
        return UUID(self._raw['channelPartner'])

    def get_attributes(self) -> Mapping[str, Any]:
        return self._raw['attributes']

    def get_name(self) -> str:
        name = self._raw['name']
        if name == '**REDACTED**':
            raise AccessToDataForbidden()
        return name

    def get_id(self) -> UUID:
        return self._id

    def get_channel_partner_access_level(self) -> 'AccessLevel':
        raw = self._raw['channelPartnerAccessLevel']
        return AccessLevel.from_raw(raw)

    def get_own_user_role(self) -> 'OrganizationUserRole':
        return OrganizationUserRole.from_raw(
            role_ids=self._raw['ownRolesIds'],
            role_names=self._raw['ownRoles'],
            permissions=self._raw['ownPermissions'],
            )

    def is_equal(self, other: 'ChannelPartnerOrganizationData') -> bool:
        names = []
        for obj in [self, other]:
            try:
                name = obj.get_name()
            except AccessToDataForbidden:
                name = 'Forbidden'
            names.append(name)
        other_access_level = other.get_channel_partner_access_level()
        return (
            self.get_id() == other.get_id()
            and names[0] == names[1]
            and self.get_channel_partner_access_level().is_equal(other_access_level)
            and self.get_own_user_role().is_equal(other.get_own_user_role())
            and self.get_attributes() == other.get_attributes()
            )


class AccessToDataForbidden(Exception):
    pass


class OrganizationUserRole:

    def __init__(self, id_: str | None, name: str | None, permissions: Collection[str] | None):
        self._id = id_
        self._name = name
        self._permissions = set(permissions) if permissions is not None else None

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self._id}, {self._name}, {self._permissions})")

    def get_id(self) -> str:
        return self._id

    @classmethod
    def from_raw(
            cls,
            role_ids: Collection[str],
            role_names: Collection[str],
            permissions: Collection[str],
            ) -> 'OrganizationUserRole':
        empty_values = list(filter(lambda x: not x, [role_ids, role_names, permissions]))
        if 0 < len(empty_values) < 3:
            raise RuntimeError(
                "Invalid organization user role data. Some fields are empty, while others are not; "
                f"role_ids: {role_ids}, role_names: {role_names}, permissions: {permissions}")
        if len(empty_values) == 3:
            return cls(None, None, None)
        # Only 1 role in organization is available to user, although role ID and role name
        # are stored as arrays.
        [role_id] = role_ids
        [role_name] = role_names
        return cls(role_id, role_name, permissions)

    def is_equal(self, other: 'OrganizationUserRole') -> bool:
        if self.is_empty() and other.is_empty():
            return True
        return (
            self._id == other._id
            and self._name == other._name
            and self._permissions == other._permissions
            )

    def is_empty(self) -> bool:
        return all(field is None for field in [self._id, self._name, self._permissions])


class Roles:

    ORGANIZATION_ADMINISTRATOR = OrganizationUserRole(
        id_='00000000-0000-4000-8000-000000000001',
        name='Organization Administrator',
        permissions=[
            'view_health_monitoring',
            'manage_systems',
            'field_access_org_admin',
            'access_systems',
            'disconnect_systems',
            'view_service_reports',
            'configure_organization',
            'manage_users',
            ],
        )
    POWER_USER = OrganizationUserRole(
        id_='00000000-0000-4000-8000-000000000003',
        name='Power User',
        permissions=[
            'field_access_org_power_user',
            'access_systems',
            'view_health_monitoring',
            ],
        )
    SYSTEM_HEALTH_VIEWER = OrganizationUserRole(
        id_='00000000-0000-4000-8000-000000000004',
        name='System Health Viewer',
        permissions=[
            "field_access_org_power_user",
            "access_systems",
            "view_health_monitoring",
            ],
        )
    VIEWER = OrganizationUserRole(
        id_='00000000-0000-4000-8000-000000000006',
        name='Viewer',
        permissions=[
            'field_access_org_other',
            'access_systems',
            ],
        )
    EMPTY = OrganizationUserRole(id_=None, name=None, permissions=None)

    @classmethod
    def get_role(cls, role_id: str):
        for role in (
                cls.ORGANIZATION_ADMINISTRATOR,
                cls.POWER_USER,
                cls.SYSTEM_HEALTH_VIEWER,
                cls.VIEWER,
                cls.EMPTY,
                ):
            if role.get_id() == role_id:
                return role
        raise RuntimeError(f"Unknown role ID {role_id} provided")


class AccessLevel:
    """Channel Partner Access Level for an Organization.

    Essentially is an organization user role that is assigned to all the users
    that were inherited from Channel Partner.
    """

    _empty = None
    _organization_admin = '00000000-0000-4000-8000-000000000001'
    _system_health_viewer = '00000000-0000-4000-8000-000000000004'

    def __init__(self, _id: str | None, role: OrganizationUserRole):
        self._id = _id
        self._role = role

    @classmethod
    def from_raw(cls, raw: str | None):
        match raw:
            case '**REDACTED**':
                raise AccessToDataForbidden()
            case cls._empty:
                id_ = cls._empty
                role = Roles.EMPTY
            case cls._organization_admin:
                id_ = cls._organization_admin
                role = Roles.ORGANIZATION_ADMINISTRATOR
            case cls._system_health_viewer:
                id_ = cls._system_health_viewer
                role = Roles.SYSTEM_HEALTH_VIEWER
            case _:
                raise RuntimeError(f"Got unexpected Channel Partner Access Level ID {raw}")
        return cls(id_, role)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._id}, {self._role!r})"

    def is_equal(self, other: 'AccessLevel'):
        return (
            self._id == other._id
            and self._role.is_equal(other._role)
            )

    @classmethod
    def empty(cls) -> 'AccessLevel':
        return cls(cls._empty, Roles.EMPTY)

    @classmethod
    def system_health_viewer(cls) -> 'AccessLevel':
        return cls(cls._system_health_viewer, Roles.SYSTEM_HEALTH_VIEWER)

    @classmethod
    def organization_admin(cls) -> 'AccessLevel':
        return cls(cls._organization_admin, Roles.ORGANIZATION_ADMINISTRATOR)

    def get_id(self) -> str | None:
        return self._id


class OrganizationUser:

    def __init__(self, raw: Mapping[str, Any]):
        self._raw = raw

    def get_role(self) -> OrganizationUserRole:
        role_ids = self._raw['rolesIds']
        # User can only have 0 or 1 role, although it is stored in an array.
        if not role_ids:
            return Roles.EMPTY
        [role_id] = role_ids
        return Roles.get_role(role_id)
