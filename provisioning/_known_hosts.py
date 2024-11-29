# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
import subprocess

from provisioning._core import Command
from provisioning._ssh import ssh


class FirstConnect(Command):

    def run(self, host):
        subprocess.run(['ssh-keygen', '-R', host])
        ssh(
            host,
            'whoami',  # An ubiquitous harmless command. Consider also "-n".
            options=[
                '-oStrictHostKeyChecking=accept-new',
                # Do not hang if a password is prompted.
                # It happens if non-interactive authentication (pubkey) fails.
                '-oBatchMode=yes',
                ])

    def __repr__(self):
        return f'{FirstConnect.__name__}()'


class AddSelfToKnownHostsOfOthers(Command):

    def __init__(self, target_user, origin_host, origin_user, command='whoami'):
        self._origin_host = origin_host
        self._origin_user = origin_user
        self._target_user = target_user
        self._command = command

    def __repr__(self):
        return f'{AddSelfToKnownHostsOfOthers.__name__}({self._target_user!r}, {self._origin_host!r}, {self._origin_user!r}, {self._command!r})'

    def run(self, host):
        _add_known_hosts(self._origin_host, self._origin_user, host, self._target_user, self._command)


class AddOtherToOurKnownHosts(Command):

    def __init__(self, our_user, their_host, their_user, command='whoami'):
        self._their_host = their_host
        self._their_user = their_user
        self._our_user = our_user
        self._command = command

    def __repr__(self):
        return f'{AddOtherToOurKnownHosts.__name__}({self._our_user!r}, {self._their_host!r}, {self._their_user!r}, {self._command!r})'

    def run(self, host):
        _add_known_hosts(host, self._our_user, self._their_host, self._their_user, self._command)


def _add_known_hosts(local_host, local_user, remote_host, remote_user, command):
    _logger.info(
        "%s: %s: Add to known hosts on %s@%s",
        remote_host, remote_user, local_user, local_host)
    ssh(local_host, shlex.join([
        'sudo', '-u', local_user,
        'ssh', f'{remote_user}@{remote_host}',
        '-o', 'StrictHostKeyChecking=accept-new',
        '-T',
        command,
        ]))


_logger = logging.getLogger(__name__)
