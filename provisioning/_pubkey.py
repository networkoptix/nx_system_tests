# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
import subprocess
from pathlib import Path

from provisioning import Command
from provisioning._ssh import ssh
from provisioning._ssh import ssh_input


class _PubKey:

    def __init__(self, data, comment=None):
        self._data = data.strip()
        self.raw = self._data + b'\n'
        [self.algo, self.body, *rest] = self._data.split(maxsplit=2)
        if comment:
            self._comment = comment
        elif rest:
            [self._comment] = rest
        else:
            self._comment = b''

    def equal(self, other: '_PubKey'):
        return (self.algo, self.body) == (other.algo, other.body)

    def __repr__(self):
        if not self._comment:
            return f'{_PubKey.__name__}({self._data!r})'
        return f'{_PubKey.__name__}({self._data!r}, {self._comment!r})'


class HomePubKey(_PubKey):

    def __init__(self, name):
        self._name = name
        path = Path.home() / '.ssh' / name
        data = Path(path).read_bytes()
        if data.startswith(b'ssh-'):
            pass
        elif data.startswith(b'--'):
            r = subprocess.run(['ssh-keygen', '-y', '-f', path], capture_output=True, check=True)
            data = r.stdout
        else:
            raise ValueError(f"Unexpected key format {path}")
        super().__init__(data)

    def __repr__(self):
        return f'{HomePubKey.__name__}({self._name!r})'


class RepoPubKey(_PubKey):

    def __init__(self, name):
        self._name = name
        path = Path(__file__).parent.parent / '_internal/keys' / name
        data = Path(path).read_bytes()
        if not data.startswith(b'ssh-'):
            raise ValueError(f"Unexpected key format {path}")
        super().__init__(data)

    def __repr__(self):
        return f'{RepoPubKey.__name__}({self._name!r})'


class CopyPubKey(_PubKey):

    def __init__(self, host, user, name):
        process = ssh(host, f'sudo -u {user} ssh-keygen -yf ~{user}/.ssh/{name}')
        super().__init__(process.stdout)


class AddPubKey(Command):

    def __init__(self, username, pubkey: '_PubKey'):
        self._username = username
        self._pubkey: _PubKey = pubkey

    def __repr__(self):
        return f'{AddPubKey.__name__}({self._username!r}, {self._pubkey!r})'

    def run(self, host):
        _logger.info("%s: %s: Update ~/.ssh/authorized_keys", host, self._username)
        u = shlex.quote(self._username)
        ssh(host, f'sudo -u {u} mkdir -m 0700 -p ~{u}/.ssh')
        ak = f'~{u}/.ssh/authorized_keys'
        stdin = self._pubkey.raw.rstrip(b'\n') + b'\n'
        ssh_input(host, f'sudo -u {u} tee -a {ak} > /dev/null', stdin=stdin)
        ssh(host, f'sudo -u {u} sort -u -o {ak} {ak}')
        # New file is created with 664 permissions due to umask. Set proper permissions.
        ssh(host, f'sudo -u {u} chmod u=rw,go= {ak}')


class RemovePubKey(Command):

    def __init__(self, username, pubkey: '_PubKey'):
        self._username = username
        self._pubkey: _PubKey = pubkey

    def __repr__(self):
        return f'{RemovePubKey.__name__}({self._username!r}, {self._pubkey!r})'

    def run(self, host):
        authorized_keys = f'~{self._username}/.ssh/authorized_keys'
        _logger.info("Remove from %s: %s", authorized_keys, self._pubkey)
        search = (self._pubkey.algo + b' ' + self._pubkey.body).decode()
        pattern = search.replace('/', '\\/')
        command = f'/{pattern}/d'
        sed = ['sed', '-i', shlex.quote(command), authorized_keys]
        sudo = ['sudo', '-u', shlex.quote(self._username), *sed]
        ssh(host, ' '.join(sudo))


_logger = logging.getLogger(__name__)
