# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
from uuid import UUID

from provisioning._core import Command
from provisioning._core import CompositeCommand
from provisioning._core import Run
from provisioning._ssh import ssh
from provisioning._ssh import ssh_still


class VirtualBoxCleanUp(Command):

    def __init__(self, user):
        self._user = user

    def __repr__(self):
        return f'{VirtualBoxCleanUp.__name__}({self._user!r})'

    def run(self, host):
        r = ssh_still(host, f'id -u {shlex.quote(self._user)}')
        if r.returncode == 1:
            _logger.info("User does not exist: %s", self._user)
            return
        r.check_returncode()
        outcome = ssh(host, ' '.join(['sudo', '-H', '-u', self._user, 'VBoxManage', 'list', 'runningvms']))
        for line in outcome.stdout.decode().strip().splitlines():
            [_name, uuid] = line.rsplit(' ', 1)
            uuid = UUID(uuid)
            ssh(host, ' '.join(['sudo', '-H', '-u', self._user, 'VBoxManage', 'controlvm', str(uuid), 'poweroff']))
        outcome = ssh(host, ' '.join(['sudo', '-H', '-u', self._user, 'VBoxManage', 'list', 'vms']))
        for line in outcome.stdout.decode().strip().splitlines():
            [_name, uuid] = line.rsplit(' ', 1)
            uuid = UUID(uuid)
            ssh(host, ' '.join(['sudo', '-H', '-u', self._user, 'VBoxManage', 'unregistervm', str(uuid), '--delete']))


class InstallVirtualBox(CompositeCommand):

    def __init__(self):
        super().__init__([
            Run('wget -N --progress=dot:giga https://download.virtualbox.org/virtualbox/7.0.20/virtualbox-7.0_7.0.20-163906~Ubuntu~jammy_amd64.deb'),
            Run("echo 'fbc338b127a13bc49a0d14145faf98324cce245e8e0c18e1b1f642bd0d54f622 *virtualbox-7.0_7.0.20-163906~Ubuntu~jammy_amd64.deb' | sha256sum -c"),
            Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ./virtualbox-7.0_7.0.20-163906~Ubuntu~jammy_amd64.deb'),
            Run('wget -N --progress=dot:giga https://download.virtualbox.org/virtualbox/7.0.20/Oracle_VM_VirtualBox_Extension_Pack-7.0.20.vbox-extpack'),
            Run("echo 'd750fb17688d70e0cb2d7b06f1ad3a661303793f4d1ac39cfa9a54806b89da25 *Oracle_VM_VirtualBox_Extension_Pack-7.0.20.vbox-extpack' | sha256sum -c"),
            InstallVboxExtpack('./Oracle_VM_VirtualBox_Extension_Pack-7.0.20.vbox-extpack'),
            ])

    def __repr__(self):
        return f'{InstallVirtualBox.__name__}()'


class InstallVboxExtpack(Command):

    def __init__(self, extpack_file: str):
        self._extpack_file = extpack_file

    def __repr__(self):
        return f'{InstallVboxExtpack.__name__}({self._extpack_file!r})'

    def run(self, host):
        r = ssh_still(
            host,
            f'sudo VBoxManage extpack install --accept-license=33d7284dc4a0ece381196fda3cfe2ed0e1e8e7ed7f27b9a9ebc4ee22e24bd23c {self._extpack_file}',
            )
        if r.returncode != 0:
            stderr = r.stderr.decode()
            if "Extension pack 'Oracle VM VirtualBox Extension Pack' is already installed" in stderr:
                return
            r.check_returncode()


_logger = logging.getLogger(__name__)
