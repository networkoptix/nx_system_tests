# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

import asyncssh

from arms.remote_control import ARMRemoteControl

_logger = logging.getLogger(__name__.split('.')[-1])


class SSHRemoteControl(ARMRemoteControl):

    def __init__(self, host: str, port: int, user: str, ssh_key: bytes):
        self._host = host
        self._port = port
        self._user = user
        self._ssh_key = ssh_key

    def _connection(self):
        return asyncssh.connect(
            host=self._host,
            port=self._port,
            username=self._user,
            client_keys=[self._ssh_key],
            known_hosts=None,
            keepalive_interval=1,
            )

    async def shutdown(self):
        async with self._connection() as connection:
            await connection.run('shutdown -P now', check=True, timeout=10)
