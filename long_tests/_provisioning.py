# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from subprocess import CalledProcessError

from provisioning import Command
from provisioning.ft_services.python_services import SystemCtl


class StopAndDisableSystemdService(Command):

    def __init__(self, ssh_user: str, service_name: str):
        self._service_name = service_name
        self._ssh_user = ssh_user

    def __repr__(self):
        return f'<{self.__class__.__name__} with {len(self._service_name)} service>'

    def run(self, host):
        try:
            SystemCtl(self._ssh_user, 'stop', self._service_name).run(host)
            SystemCtl(self._ssh_user, 'disable', self._service_name).run(host)
        except CalledProcessError:
            pass  # The service does not exist yet.
