# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import ExitStack
from typing import Tuple
from uuid import UUID

from installation import Mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import create_smb_share
from os_access import OsAccess
from os_access import RemotePath

_logger = logging.getLogger(__name__)


class SMBStand:

    def __init__(
            self,
            mediaserver: Mediaserver,
            smb_os_access: OsAccess,
            smb_address: str,
            smb_username: str,
            smb_password: str,
            ):
        self._mediaserver: Mediaserver = mediaserver
        self._smb_os_access: OsAccess = smb_os_access
        self._smb_address: str = smb_address
        self._smb_username: str = smb_username
        self._smb_password: str = smb_password
        [self._smb_share_name, self._smb_path] = create_smb_share(
            self._smb_os_access, self._smb_username, self._smb_password, 300 * 1024**3, 'P')

    def add_storage(self) -> UUID:
        return self.mediaserver().api.add_smb_storage(
            self._smb_address,
            self._smb_share_name,
            self._smb_username,
            self._smb_password,
            )

    def mount(self, mount_point: RemotePath):
        self._mediaserver.os_access.mount_smb_share(
            mount_point=mount_point,
            path=f'//{self._smb_address}/{self._smb_share_name}',
            username=self._smb_username,
            password=self._smb_password,
            )

    def mediaserver(self) -> Mediaserver:
        return self._mediaserver

    def smb_os_access(self) -> OsAccess:
        return self._smb_os_access

    def smb_share_name(self) -> str:
        return self._smb_share_name

    def smb_address(self) -> str:
        return self._smb_address

    def smb_username(self) -> str:
        return self._smb_username


def smb_stand(
        two_vm_types: Tuple[str, str],
        pool: FTMachinePool,
        exit_stack: ExitStack,
        smb_credentials: Tuple[str, str] = ('UserWithPassword', 'GoodPassword'),
        ) -> SMBStand:
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    [user, password] = smb_credentials
    return SMBStand(
        mediaserver,
        smb_machine.os_access,
        smb_address,
        user,
        password,
        )
