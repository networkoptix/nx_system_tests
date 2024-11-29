# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Sequence
from typing import NamedTuple
from typing import Optional

from _internal.ldap_generated_credentials import DEFAULT_LDAP_USER_PASSWORD
from os_access import OsAccess


class _Resource(NamedTuple):
    dn: Sequence[tuple[str, str]]
    classes: Collection[str]
    attributes: Sequence[tuple[str, str]]


class _UserAttrs(NamedTuple):
    uid: str
    password: str
    first_name: str
    second_name: str
    full_name: str
    display_name: str
    email: Optional[str]


class LDAPServerInstallation(metaclass=ABCMeta):

    def __init__(self, os_access: OsAccess):
        self._os_access = os_access

    @abstractmethod
    def domain(self):
        pass

    @abstractmethod
    def admin_dn(self):
        pass

    @abstractmethod
    def password(self):
        pass

    @abstractmethod
    def users_ou(self):
        pass

    @abstractmethod
    def groups_ou(self):
        pass

    @abstractmethod
    def ou_huge(self) -> 'PresetOuParams':
        pass

    @abstractmethod
    def non_default_group_object_class(self):
        pass

    @abstractmethod
    def make_initial_setup(self):
        pass

    @abstractmethod
    def add_users(self, user_list: Collection[_UserAttrs]):
        pass

    @abstractmethod
    def add_group(
            self,
            name: str,
            *,
            members: Optional[Collection[str]] = None,
            subgroups: Optional[Collection[str]] = None,
            ):
        pass

    @abstractmethod
    def add_group_with_non_default_object_class(self, name: str):
        pass

    @abstractmethod
    def change_uid(self, current_uid: str, new_uid: str):
        pass

    @abstractmethod
    def rename_group(self, current_name: str, new_name: str):
        pass

    @abstractmethod
    def add_user_to_group(self, member_uid: str, group_name: str):
        pass

    @abstractmethod
    def remove_user_from_group(self, member_uid: str, group_name: str):
        pass

    @abstractmethod
    def change_user_email(self, uid: str, email: str):
        pass

    @abstractmethod
    def wait_until_ready(self):
        pass

    @abstractmethod
    def configure_tls(self, hostname: str):
        pass


class GeneratedLDAPUser:
    """Object to represent a user in LDAP server.

    >>> ldap_user = GeneratedLDAPUser('Test', 'User')
    >>> assert ldap_user.uid == 'test_user', ldap_user.uid
    >>> assert ldap_user.password == 'WellKnownPassword2!', ldap_user.password
    >>> assert ldap_user.full_name == 'Test User', ldap_user.full_name
    >>> assert ldap_user.email == 'test_user@example.com', ldap_user.email
    >>> ldap_user = GeneratedLDAPUser('Test', 'User', has_email=False)
    >>> assert ldap_user.email is None, ldap_user.email
    """

    def __init__(self, first_name: str, second_name: str, has_email: bool = True):
        self.uid = f'{first_name.lower()}_{second_name.lower()}'
        self.password = DEFAULT_LDAP_USER_PASSWORD
        self._first_name = first_name
        self._second_name = second_name
        self.full_name = f'{first_name} {second_name}'
        self._display_name = f'{first_name} {second_name}'
        self.email = f'{first_name.lower()}_{second_name.lower()}@example.com' if has_email else None

    def __repr__(self):
        return f'{__class__.__name__}({self.full_name!r})'

    def attrs(self):
        return _UserAttrs(
            uid=self.uid,
            password=self.password,
            first_name=self._first_name,
            second_name=self._second_name,
            full_name=self.full_name,
            display_name=self._display_name,
            email=self.email,
            )


class PresetOuParams(NamedTuple):
    ou_name: str
    dn: str
    count_groups: int
    count_users: int


_logger = logging.getLogger(__name__)
