# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import logging
import time
from collections.abc import Collection
from itertools import islice
from pathlib import Path
from string import Template
from typing import Optional

from os_access import WindowsAccess
from os_access._powershell import PowershellError
from os_access._powershell import run_powershell_script
from os_access.ldap.server_installation._ldap_server_interface import LDAPServerInstallation
from os_access.ldap.server_installation._ldap_server_interface import PresetOuParams
from os_access.ldap.server_installation._ldap_server_interface import _UserAttrs


class ActiveDirectoryInstallation(LDAPServerInstallation):

    _default_port = 389
    _os_access: WindowsAccess

    def __init__(self, os_access: WindowsAccess):
        super().__init__(os_access)
        self._base_dn = [('dc', 'local'), ('dc', 'nx')]
        users_cn = [('cn', 'Users')] + self._base_dn
        self._admin_dn = [('cn', 'Administrator')] + users_cn
        self._ou_name = 'LdapUsers'
        self._users_ou = [('ou', self._ou_name)] + self._base_dn
        self._groups_ou = [('ou', self._ou_name)] + self._base_dn
        # Provisionally prepared OI with a large numbers of users and groups.
        # Users: from test_user_000001 to test_user_090000
        # Groups: from test_group_00001 to test_group_10000
        self._ou_huge = PresetOuParams(
            'LdapUsersHuge',
            self._serialize_dn([('ou', 'LdapUsersHuge')] + self._base_dn),
            count_groups=10000,
            count_users=90000,
            )

    def __repr__(self):
        port = self._os_access.get_port('tcp', self._default_port)
        return f'{__class__.__name__} at {self._os_access.address}:{port}'

    @staticmethod
    def _serialize_dn(dn: Collection[tuple[str, str]]) -> str:
        """Represents LDAP DN as a string.

        >>> ActiveDirectoryInstallation._serialize_dn([('dc', 'local'), ('dc', 'nx')])
        'dc=local,dc=nx'
        >>> ActiveDirectoryInstallation._serialize_dn([('uid', 10001), ('ou', 'Users'), ('dc', 'local'), ('dc', 'nx')])
        'uid=10001,ou=Users,dc=local,dc=nx'
        """
        return ','.join(('='.join((k, str(v))) for k, v in dn))

    def domain(self):
        return 'local.nx'

    def admin_dn(self):
        return self._serialize_dn(self._admin_dn)

    def password(self):
        return 'WellKnownPassword1!@#'

    def users_ou(self):
        return self._serialize_dn(self._users_ou)

    def groups_ou(self):
        return self._serialize_dn(self._groups_ou)

    def ou_huge(self) -> PresetOuParams:
        return self._ou_huge

    def non_default_group_object_class(self):
        return 'posixGroupTest'

    def make_initial_setup(self):
        """Make the initial setup needed to run the Active Directory installation.

        There is a default group CN=Users,DC=local,DC=nx, that contains Administrator.
        To exclude this user in tests, create another group OU=LDAPUsers,DC=local,DC=nx,
        """
        run_powershell_script(
            self._os_access.winrm_shell(),
            '''
                New-ADOrganizationalUnit -Name "$ou" -Path "$base_dn"
            ''',
            variables={
                'ou': self._ou_name,
                'base_dn': self._serialize_dn(self._base_dn),
                })
        # Generate users and groups in the separate OU
        run_powershell_script(
            self._os_access.winrm_shell(),
            'New-ADOrganizationalUnit -Name "$ou" -Path "$base_dn"',
            variables={'ou': self._ou_huge.ou_name, 'base_dn': self._serialize_dn(self._base_dn)},
            )
        self._bulk_create_groups(self._ou_huge.ou_name, self._ou_huge.count_groups)
        self._bulk_create_users(self._ou_huge.ou_name, self._ou_huge.count_users, self.password())
        self._synchronize()

    def add_users(self, user_list: Collection[_UserAttrs]):
        for user in user_list:
            run_powershell_script(
                self._os_access.winrm_shell(),
                '''
                    $secure_pwd = ConvertTo-SecureString $password -AsPlainText -Force
                    New-ADUser `
                    -Name "$full_name" `
                    -GivenName "$given_name" `
                    -Surname "$surname" `
                    -SamAccountName "$uid" `
                    -UserPrincipalName "$uid" `
                    -EmailAddress "$email" `
                    -Path "$path" `
                    -AccountPassword $secure_pwd `
                    -Enabled $true
                ''',
                variables={
                    'full_name': user.full_name,
                    'given_name': user.first_name,
                    'surname': user.second_name,
                    'uid': user.uid,
                    'email': user.email,
                    'path': self._serialize_dn(self._users_ou),
                    'password': user.password,
                    },
                )

    def add_group(
            self,
            name: str,
            *,
            members: Optional[Collection[str]] = None,
            subgroups: Optional[Collection[str]] = None,
            ):
        run_powershell_script(
            self._os_access.winrm_shell(),
            'New-ADGroup -Name $group_name -Path $path -GroupScope Global',
            variables={'group_name': name, 'path': self._serialize_dn(self._groups_ou)},
            )
        if members is not None or subgroups is not None:
            members = members or []
            subgroups = subgroups or []
            run_powershell_script(
                self._os_access.winrm_shell(),
                'Add-ADGroupMember -Identity $group_name -Members $members',
                variables={'group_name': name, 'members': [*members, *subgroups]},
                )

    def add_group_with_non_default_object_class(self, name: str):
        self._create_custom_class(self.non_default_group_object_class())
        run_powershell_script(
            self._os_access.winrm_shell(),
            'New-ADObject -Name $group_name -Path $path -type $class_name -PassThru',
            variables={
                'group_name': name,
                'path': self._serialize_dn(self._groups_ou),
                'class_name': self.non_default_group_object_class(),
                })

    def change_uid(self, current_uid: str, new_uid: str):
        run_powershell_script(
            self._os_access.winrm_shell(),
            'set-ADuser -identity $current_uid -Replace @{SamAccountName=$new_uid}',
            variables={'current_uid': current_uid, 'new_uid': new_uid},
            )

    def rename_group(self, current_name: str, new_name: str):
        run_powershell_script(
            self._os_access.winrm_shell(),
            'Get-ADGroup -Identity $current_name | Rename-ADObject -NewName $new_name',
            variables={'current_name': current_name, 'new_name': new_name},
            )

    def add_user_to_group(self, member_uid: str, group_name: str):
        run_powershell_script(
            self._os_access.winrm_shell(),
            'Add-ADGroupMember -Identity $group_name -Members $members',
            variables={'group_name': group_name, 'members': [member_uid]},
            )

    def remove_user_from_group(self, member_uid: str, group_name: str):
        raise NotImplementedError()

    def change_user_email(self, uid: str, email: str):
        run_powershell_script(
            self._os_access.winrm_shell(),
            'set-ADuser $uid -email $email',
            variables={'uid': uid, 'email': email},
            )

    def wait_until_ready(self):
        finished_at = time.monotonic() + 120
        while True:
            try:
                run_powershell_script(self._os_access.winrm_shell(), 'Get-ADDomain', {})
            except PowershellError as exc:
                if 'Server instance not found on the given port' in exc.message:
                    if time.monotonic() < finished_at:
                        _logger.info("Waiting for Active Directory services to start")
                        time.sleep(5)
                        continue
                raise
            else:
                break

    def configure_tls(self, hostname: str):
        raise NotImplementedError("Not implemented yet")

    def _create_custom_class(self, class_name: str):
        result = run_powershell_script(
            self._os_access.winrm_shell(),
            'Get-ADObject -SearchBase "$((Get-ADRootDSE).SchemaNamingContext)" -Filter {lDAPDisplayName -eq $class_name}',
            variables={'class_name': self.non_default_group_object_class()},
            )
        _logger.debug("Result of finding the custom class %s: %r", class_name, result)
        if not result:
            import_class_template_file = Path(__file__).with_name('create_class_ad_template.ldf')
            import_class_template = Template(import_class_template_file.read_text())
            self._import_ldif('create_class', import_class_template.substitute(class_name=class_name))

    def _bulk_create_groups(self, ou: str, groups_count: int):
        started_at = time.monotonic()
        _logger.info('%r: creating %d groups', self, groups_count)
        template_file = Path(__file__).with_name('create_group_ad_template.ldf')
        template = Template(template_file.read_text())
        groups = [f'test_group_{group_no:05d}' for group_no in range(1, groups_count + 1)]
        import_script = [template.substitute(ou=ou, group_name=group_name) for group_name in groups]
        self._import_ldif('create_groups', '\n'.join(import_script))
        _logger.info('%r: operation finished. It took %d seconds', self, time.monotonic() - started_at)

    def _bulk_create_users(self, ou: str, users_count: int, password: str):
        # The flags in the userAccountControl field control user type and user properties.
        # See: https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties
        started_at = time.monotonic()
        _logger.info('%r: creating %d users', self, users_count)
        template_file = Path(__file__).with_name('create_user_ad_template.ldf')
        template = Template(template_file.read_text())
        users = [f'test_user_{user_no:06d}' for user_no in range(1, users_count + 1)]
        encoded_password = _encode_password(password)
        batch_no = 0
        users_by_batch = 10000
        while len(users) > batch_no * users_by_batch:
            users_batch = islice(users, batch_no * users_by_batch, (batch_no + 1) * users_by_batch)
            import_script = [template.substitute(
                ou=ou, user_name=user_name, password=encoded_password) for user_name in users_batch]
            self._import_ldif(f'create_users_{batch_no:03d}', '\n'.join(import_script))
            batch_no += 1
        _logger.info('%r: operation finished. It took %d seconds', self, time.monotonic() - started_at)

    def _synchronize(self):
        synchronize_imported_records = (
            'dn:\n'
            'changetype: modify\n'
            'add: schemaUpdateNow\n'
            'schemaUpdateNow: 1\n'
            '-\n'
            )
        self._import_ldif('sync', synchronize_imported_records)

    def _import_ldif(self, script_name: str, script: str):
        # See: https://www.rfc-editor.org/rfc/rfc2849.txt
        # See: https://www.unicloud.com.au/using-ldifde-to-exportimport-active-directory/
        # See: https://www.getacluesolutions.com/ldifde/
        script_file = self._os_access.path(rf'c:\_ldifde\{script_name}.ldf')
        script_file.parent.mkdir(exist_ok=True)
        script_file.write_text(script)
        wait_time = 5
        # Using the option -h (Enable SASL layer signing and encryption) is obligatory for changing
        # a password.
        command_line = ['ldifde', '-j', script_file.parent, '-h', '-k', '-i', '-f', script_file]
        with self._os_access.winrm_shell().Popen(command_line) as run:
            while True:
                time.sleep(wait_time)
                run.receive(timeout_sec=1)
                if run.returncode is None:
                    wait_time = min(60.0, wait_time * 1.5)
                elif run.returncode == 0:
                    return
                else:
                    for log_file_err in script_file.parent.glob('*.err'):
                        _logger.error(
                            '%r: import log file %s:\n%s',
                            self, log_file_err.name, log_file_err.read_text())
                    raise RuntimeError('%r: import process finished with exit code %s', self, run.returncode)


def _encode_password(password: str) -> str:
    # The password should be surrounded double quotations and encoded to UTF-16LE.
    # See: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/6e803168-f140-4d23-b2d3-c3a8ab5917d2
    # The password must be surrounded double quotations. ActiveDirectory simply removes quotations
    # at both ends and does not change quotations inside the password string (if they exist).
    # There is no reliable information about this requirement, but the assumption is that it's a
    # defensive measure against illegal encoding or corruption of the password string.
    quoted_password = '"' + password + '"'
    # The quoted password should be encoded as a UCS-2LE string. UCS-2 is an earlier version of
    # UTF-16 and is mostly compatible with it.
    # See: https://www.eyrie.org/~eagle/journal/2007-07/010.html
    encoded_password = quoted_password.encode('utf-16_le')
    # An encoded UTF-16 string is a byte string. It should be encoded as BASE64 to be used in a
    # text protocol.
    return base64.b64encode(encoded_password).decode('ascii')


_logger = logging.getLogger(__name__)
