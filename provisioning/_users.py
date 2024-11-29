# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
import subprocess

from provisioning._core import Command
from provisioning._core import Run
from provisioning._ssh import ssh_input
from provisioning._ssh import ssh_still


class AddUser(Command):

    def __init__(self, username):
        self._username = username

    def __repr__(self):
        return f'{AddUser.__name__}({self._username!r})'

    def run(self, host):
        u = shlex.quote(self._username)
        r = ssh_still(host, f'sudo useradd {u} -m -s /bin/bash')
        if r.returncode == 0:
            _logger.info("%s: %s: user added", host, self._username)
        else:
            if b'exist' in r.stderr.lower():
                _logger.info("%s: %s: user already exists", host, self._username)
            else:
                _logger.error("%s: %s: failure: %s", host, self._username, r.stderr)
                raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)


class RemoveUser(Command):

    def __init__(self, username: str):
        self._user = username

    def __repr__(self):
        return f'{RemoveUser.__name__}({self._user!r})'

    def run(self, host):
        self._kill_processes(host)
        self._delete_user(host)
        self._delete_group(host)  # In case other users were in user group.

    def _delete_user(self, host):
        r = ssh_still(host, f'sudo userdel -f {shlex.quote(self._user)}')
        if b'does not exist' in r.stderr.lower():
            _logger.info("User does not exist: %s", self._user)
        elif r.returncode == 0:
            _logger.info("User deleted: %s", self._user)
        else:
            r.check_returncode()

    def _delete_group(self, host):
        r = ssh_still(host, f'sudo groupdel {shlex.quote(self._user)}')
        if b'does not exist' in r.stderr.lower():
            _logger.info("Group does not exist: %s", self._user)
        elif r.returncode == 0:
            _logger.info("Group deleted: %s", self._user)
        else:
            r.check_returncode()

    def _kill_processes(self, host):
        """Kill processes started by user.

        They may remain defunct (zombie) waiting to be reaped.
        """
        r = ssh_still(host, f'sudo killall -9 --user {shlex.quote(self._user)}')
        if r.returncode == 1 and not r.stderr:
            _logger.info("No processes by user: %s", self._user)
        elif b'cannot find user' in r.stderr.lower():
            _logger.info("No user: %s", self._user)
        elif r.returncode == 0:
            _logger.info("Processes terminated: %s", r.stderr.decode())
        else:
            r.check_returncode()


class AddGroup(Command):

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return f'{AddGroup.__name__}({self._name!r})'

    def run(self, host):
        r = ssh_still(host, f'sudo groupadd {shlex.quote(self._name)}')
        if r.returncode == 0:
            _logger.info("%s: %s: group added", host, self._name)
        else:
            if b'already exists' in r.stderr.lower():
                _logger.info("%s: %s: group already exists", host, self._name)
            else:
                _logger.error("%s: %s: failure: %s", host, self._name, r.stderr)
                raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)


class AddUserToGroup(Run):

    def __init__(self, username, group):
        super().__init__(f'sudo usermod -aG {shlex.quote(group)} {shlex.quote(username)}')


class RemoveUserFromGroup(Run):

    def __init__(self, username, group):
        super().__init__(f'sudo gpasswd -d {shlex.quote(username)} {shlex.quote(group)}')


class NewUsers(Command):

    def __init__(self, users: str):
        self._users = users

    def run(self, host):
        ssh_input(host, 'sudo newusers', stdin=self._users.encode('utf8'))


_logger = logging.getLogger(__name__)
