# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import logging
import string
import time
from collections.abc import Collection
from typing import Optional

from ca import default_ca
from os_access import PosixAccess
from os_access import RemotePath
from os_access.ldap.server_installation._ldap_server_interface import LDAPServerInstallation
from os_access.ldap.server_installation._ldap_server_interface import _Resource
from os_access.ldap.server_installation._ldap_server_interface import _UserAttrs


class OpenLDAPInstallation(LDAPServerInstallation):

    _default_port = 389

    def __init__(self, os_access: PosixAccess):
        super().__init__(os_access)
        self._service = os_access.service('slapd')
        self._password = 'WellKnownPassword2'
        self._uri = 'ldap://ldap.local.nx'
        self._domain = 'local.nx'
        self._base_dn = [('dc', 'local'), ('dc', 'nx')]
        self._admin_dn = [('cn', 'admin')] + self._base_dn
        self._users_ou = [('ou', 'Users')] + self._base_dn
        self._groups_ou = [('ou', 'Groups')] + self._base_dn
        self._non_default_group_object_class = 'posixGroup'
        self._free_gid_number = 10000

    def __repr__(self):
        port = self._os_access.get_port('tcp', self._default_port)
        return f'{__class__.__name__} at {self._os_access.address}:{port}'

    @staticmethod
    def _serialize_dn(dn: Collection[tuple[str, str]]) -> str:
        """Represents LDAP DN as a string.

        >>> OpenLDAPInstallation._serialize_dn([('dc', 'local'), ('dc', 'nx')])
        'dc=local,dc=nx'
        >>> OpenLDAPInstallation._serialize_dn([('uid', 10001), ('ou', 'Users'), ('dc', 'local'), ('dc', 'nx')])
        'uid=10001,ou=Users,dc=local,dc=nx'
        """
        return ','.join(('='.join((k, str(v))) for k, v in dn))

    def domain(self):
        return self._domain

    def admin_dn(self):
        return self._serialize_dn(self._admin_dn)

    def password(self):
        return self._password

    def users_ou(self):
        return self._serialize_dn(self._users_ou)

    def groups_ou(self):
        return self._serialize_dn(self._groups_ou)

    def ou_huge(self):
        raise NotImplementedError()

    def non_default_group_object_class(self):
        return self._non_default_group_object_class

    def make_initial_setup(self):
        self._set_ldap_conf()
        self._service.stop()
        self._service.start()
        self._set_root_dn_password()
        self._add_users_ou()
        self._add_groups_ou()

    def _set_ldap_conf(self):
        config = (
            f'BASE {self._serialize_dn(self._base_dn)}\n'
            f'URI {self._uri}\n'
            'TLS_CACERT /etc/ssl/certs/ca-certificates.crt\n'
            )
        path: RemotePath = self._os_access.path('/etc/ldap/ldap.conf')
        path.write_text(config)
        slapd_config_file = self._os_access.path('/etc/default/slapd')
        slapd_config = slapd_config_file.read_text().splitlines()
        for line_no in range(len(slapd_config)):
            if slapd_config[line_no].startswith('SLAPD_SERVICES'):
                slapd_config[line_no] = 'SLAPD_SERVICES="ldap:/// ldapi:/// ldaps:///"'
                break
        slapd_config_file.write_text('\n'.join(slapd_config))

    def _set_root_dn_password(self):
        password_hash = self._os_access.run(['slappasswd', '-s', self._password]).stdout.decode('ascii').rstrip()
        mdb_dn = self._serialize_dn([('olcDatabase', '{1}mdb'), ('cn', 'config')])
        change_mdb_password_ldif = _make_ldif([
            ('dn', mdb_dn),
            ('changetype', 'modify'),
            ('replace', 'olcRootPW'),
            ('olcRootPW', password_hash),
            ])
        self._ldapmodify(change_mdb_password_ldif)
        config_dn = self._serialize_dn([('olcDatabase', '{0}config'), ('cn', 'config')])
        change_config_password_ldif = _make_ldif([
            ('dn', config_dn),
            ('changetype', 'modify'),
            ('replace', 'olcRootPW'),
            ('olcRootPW', password_hash),
            ])
        self._ldapmodify(change_config_password_ldif)

    def _ldapmodify(self, ldif):
        _logger.debug('Applying LDIF via ldapmodify on LDAP server %r:\n%s', self, ldif)
        self._os_access.run(
            [
                'ldapmodify',
                '-Y', 'EXTERNAL',  # Use SASL EXTERNAL authentication
                '-H', 'ldapi:///',  # Configure using local Unix socket
                ],
            input=ldif.encode('utf-8'),
            )

    def _ldapmodify_by_admin(self, ldif):
        _logger.debug('Applying LDIF via ldapmodify by admin on LDAP server %r:\n%s', self, ldif)
        self._os_access.run(
            [
                'ldapmodify',
                '-x',  # Use simple authentication instead of SASL
                '-H', 'ldapi:///',  # Configure using local Unix socket
                '-D', self._serialize_dn(self._admin_dn),
                '-w', self._password,
                ],
            input=ldif.encode('utf-8'),
            )

    def _ldapadd(self, ldif):
        _logger.debug('Applying LDIF via ldapadd on LDAP server %r:\n%s', self, ldif)
        self._os_access.run(
            [
                'ldapadd',
                '-x',  # Use simple authentication instead of SASL
                '-H', 'ldapi:///',  # Configure using local Unix socket
                '-D', self._serialize_dn(self._admin_dn),
                '-w', self._password,
                ],
            input=ldif.encode('utf-8'),
            )

    def _add_users_ou(self):
        ldif = _make_ldif([
            ('dn', (self._serialize_dn(self._users_ou))),
            ('objectClass', 'organizationalUnit'),
            ('ou', 'Users'),
            ])
        self._ldapadd(ldif)

    def _add_groups_ou(self):
        ldif = _make_ldif([
            ('dn', (self._serialize_dn(self._groups_ou))),
            ('objectClass', 'organizationalUnit'),
            ('ou', 'Groups'),
            ])
        self._ldapadd(ldif)

    def _add_resources(self, resources: Collection[_Resource]):
        """Adding multiple resources at once is much faster than adding them one by one."""
        ldif = ''
        for dn, classes, attributes in resources:
            ldif += _make_ldif([
                ('dn', self._serialize_dn(dn)),
                *(('objectClass', c) for c in classes),
                *attributes,
                ])
            ldif += '\n\n'
        _logger.debug("Adding %d resources to %r", len(resources), self)
        self._ldapadd(ldif)

    def configure_tls(self, hostname: str):
        key, cert = default_ca().generate_key_and_cert_pair(hostname)
        cert_dir = self._os_access.path('/etc/ldap/certs')
        cert_dir.mkdir()
        ldap_cert_file = cert_dir / 'ldap.crt'
        ldap_cert_file.write_text(cert)
        ldap_key_file = cert_dir / 'ldap.key'
        ldap_key_file.write_text(key)
        ldif = [
            _make_ldif([
                ('dn', 'cn=config'),
                ('changetype', 'modify'),
                ('add', 'olcTLSCertificateFile'),
                ('olcTLSCertificateFile', str(ldap_cert_file)),
                ]),
            '-',
            _make_ldif([
                ('add', 'olcTLSCertificateKeyFile'),
                ('olcTLSCertificateKeyFile', str(ldap_key_file)),
                ]),
            ]
        self._ldapmodify('\n'.join(ldif))

    def add_users(self, user_list: Collection[_UserAttrs]):
        resource_list = []
        for user in user_list:
            dn = [('uid', user.uid), *self._users_ou]
            classes = ['inetOrgPerson']
            attrs = [
                ('uid', user.uid),
                ('sn', user.second_name),
                ('givenName', user.first_name),
                ('cn', user.full_name),
                ('displayName', user.display_name),
                ('userPassword', user.password),
                ]
            if user.email is not None:
                attrs.append(('mail', user.email))
            resource_list.append(_Resource(dn, classes, attrs))
        self._add_resources(resource_list)

    def add_group(
            self,
            name: str,
            *,
            members: Optional[Collection[str]] = None,
            subgroups: Optional[Collection[str]] = None,
            ):
        attributes = [('cn', name)]
        if members is not None:
            for member in members:
                member_dn = self._serialize_dn([('uid', member), *self._users_ou])
                attributes.append(('member', member_dn))
        if subgroups is not None:
            for group_name in subgroups:
                group_dn = self._serialize_dn([('cn', group_name), *self._groups_ou])
                attributes.append(('member', group_dn))
        if members is None and subgroups is None:
            # At least one member is required. Add admin for simplicity.
            attributes.append(('member', self.admin_dn()))
        resource = _Resource(
            dn=[('cn', name), *self._groups_ou],
            classes=['groupOfNames'],
            attributes=attributes,
            )
        self._add_resources([resource])

    def add_group_with_non_default_object_class(self, name: str):
        self._add_posix_group(name)

    def _add_posix_group(self, name: str):
        resource = _Resource(
            dn=[('cn', name), *self._groups_ou],
            classes=[self._non_default_group_object_class],
            attributes=[
                ('cn', name),
                ('gidNumber', str(self._free_gid_number)),
                ],
            )
        self._add_resources([resource])
        self._free_gid_number += 1

    def change_uid(self, current_uid: str, new_uid: str):
        dn = [('uid', current_uid), *self._users_ou]
        ldif = _make_ldif([
            ('dn', self._serialize_dn(dn)),
            ('changetype', 'modrdn'),
            ('newrdn', self._serialize_dn([('uid', new_uid)])),
            ('deleteoldrdn', '1'),  # Replace user, not duplicate
            ])
        self._ldapmodify_by_admin(ldif)

    def rename_group(self, current_name: str, new_name: str):
        dn = [('cn', current_name), *self._groups_ou]
        ldif = _make_ldif([
            ('dn', self._serialize_dn(dn)),
            ('changetype', 'modrdn'),
            ('newrdn', self._serialize_dn([('cn', new_name)])),
            ('deleteoldrdn', '1'),  # Replace group, not duplicate
            ])
        self._ldapmodify_by_admin(ldif)

    def add_user_to_group(self, member_uid: str, group_name: str):
        group_dn = [('cn', group_name), *self._groups_ou]
        users_dn = [('uid', member_uid), *self._users_ou]
        ldif = _make_ldif([
            ('dn', self._serialize_dn(group_dn)),
            ('changetype', 'modify'),
            ('add', 'member'),
            ('member', self._serialize_dn(users_dn)),
            ])
        self._ldapmodify_by_admin(ldif)

    def remove_user_from_group(self, member_uid: str, group_name: str):
        group_dn = [('cn', group_name), *self._groups_ou]
        users_dn = [('uid', member_uid), *self._users_ou]
        ldif = _make_ldif([
            ('dn', self._serialize_dn(group_dn)),
            ('changetype', 'modify'),
            ('delete', 'member'),
            ('member', self._serialize_dn(users_dn)),
            ])
        self._ldapmodify_by_admin(ldif)

    def change_user_email(self, uid: str, email: str):
        dn = [('uid', uid), *self._users_ou]
        ldif = _make_ldif([
            ('dn', self._serialize_dn(dn)),
            ('changetype', 'modify'),
            ('replace', 'mail'),
            ('mail', email),
            ])
        self._ldapmodify_by_admin(ldif)

    def wait_until_ready(self):
        finished_at = time.monotonic() + 30
        while not self._service.status().is_running:
            if time.monotonic() < finished_at:
                _logger.info("Waiting for OpenLDAP service to start")
                time.sleep(5)
                continue
            else:
                raise RuntimeError("OpenLDAP service failed to start")


def _make_ldif_line(key, value):
    r"""Make LDIF formatted line.

    If a value contains a non-printing character, or begins with  a  space
    or  a  colon  ':', the <attrtype> is followed by a double colon and the
    value is encoded in base 64 notation.

    See: https://www.openldap.org/software/man.cgi?query=ldif

    >>> _make_ldif_line('sn', 'Test')
    'sn: Test'
    >>> _make_ldif_line('sn', '\N{CYRILLIC SMALL LETTER YA}')
    'sn:: 0Y8='
    >>> _make_ldif_line('sn', ' Test')
    'sn:: IFRlc3Q='
    >>> _make_ldif_line('sn', ':Test')
    'sn:: OlRlc3Q='
    >>> _make_ldif_line('sn', 'Te\nst')
    'sn:: VGUKc3Q='
    """
    _allowed = frozenset(string.ascii_letters + string.digits + string.punctuation + ' ')
    if _allowed.issuperset(value) and not value.startswith((' ', ':')):
        return f'{key}: {value}'
    else:
        return f'{key}:: {base64.b64encode(value.encode("utf-8")).decode("ascii")}'


def _make_ldif(attrs: Collection[tuple[str, str]]) -> str:
    r"""Make LDIF formatted string.

    See: https://www.openldap.org/software/man.cgi?query=ldif

    >>> data = [('dn', 'cn=c'), ('changetype', 'modify'), ('replace', 'PW'), ('PW', 'qwe')]
    >>> _make_ldif(data)
    'dn: cn=c\nchangetype: modify\nreplace: PW\nPW: qwe'
    """
    return '\n'.join(_make_ldif_line(key, value) for key, value in attrs)


_logger = logging.getLogger(__name__)
