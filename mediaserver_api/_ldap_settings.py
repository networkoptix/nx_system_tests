# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Mapping
from enum import Enum
from typing import Any
from typing import NamedTuple
from typing import Optional


class LdapSearchBase(NamedTuple):
    base_dn: str
    filter: str
    name: str


class LdapContinuousSyncMode(Enum):
    DISABLED = 'disabled'
    GROUPS_ONLY = 'groupsOnly'
    USERS_AND_GROUPS = 'usersAndGroups'


class _LdapSettings(metaclass=ABCMeta):

    PORT = 389

    @abstractmethod
    def as_dict(self) -> Mapping[str, Any]:
        pass

    @staticmethod
    def _ldap_uri(host: str, port: int):
        return f'ldap://{host}:{port}'


class _LdapSettingsV0(_LdapSettings):

    def __init__(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]],
            ):
        self._host = host
        self._admin_dn = admin_dn
        self._admin_password = admin_password
        self._search_base = search_base or []

    def as_dict(self) -> Mapping[str, Any]:
        settings = {
            'ldapAdminDn': self._admin_dn,
            'ldapAdminPassword': self._admin_password,
            'ldapUri': self._ldap_uri(self._host, self.PORT),
            }
        if self._search_base:
            # In old API only one search base is supported.
            [search_base] = self._search_base
            settings['ldapSearchBase'] = search_base.base_dn
        return settings


class _LdapSettingsV3(_LdapSettings):

    def __init__(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]],
            login_attribute: Optional[str] = None,
            group_object_class: Optional[str] = None,
            remove_records: bool = False,
            sync_mode: LdapContinuousSyncMode = LdapContinuousSyncMode.DISABLED,
            ):
        self._host = host
        self._admin_dn = admin_dn
        self._admin_password = admin_password
        self._search_base = search_base or []
        self._login_attribute = login_attribute
        self._group_object_class = group_object_class
        self._remove_records = remove_records
        self._sync_mode = sync_mode

    def as_dict(self) -> Mapping[str, Any]:
        filters = []
        for search_base in self._search_base:
            filters.append(
                {'base': search_base.base_dn, 'filter': search_base.filter, 'name': search_base.name})
        settings = {
            'adminDn': self._admin_dn,
            'adminPassword': self._admin_password,
            'uri': self._ldap_uri(self._host, self.PORT),
            'filters': filters,
            'loginAttribute': self._login_attribute or '',
            'groupObjectClass': self._group_object_class or '',
            'continuousSync': self._sync_mode.value,
            'removeRecords': self._remove_records,  # Delete users and groups from the old LDAP connection
            }
        return settings
