# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from typing import AsyncContextManager
from typing import Mapping

_logger = logging.getLogger(__name__.split('.')[-1])
_control_socket_path = "/tmp/qcow2target.sock"


ATTACH = 'ATTACH'
DETACH_LUN = 'DETACHLUN'
ADD_TARGET = 'ADDTARGET'
DELETE_TARGET = 'DELETETARGET'
CLEAR_TARGET = 'CLEARTARGET'
LIST = 'LIST'


class Qcow2TargetError(Exception):

    def __init__(self, message):
        super(Qcow2TargetError, self).__init__(message)


@asynccontextmanager
async def _control_session() -> AsyncContextManager[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    reader, writer = await asyncio.open_unix_connection(_control_socket_path)
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


async def _iscsi_qcow2_request(request: Mapping[str, Any]) -> Mapping[str, Any]:
    async with _control_session() as (reader, writer):
        response_text = json.dumps(request) + '\n'
        writer.write(response_text.encode('utf-8'))
        response_text = await reader.readline()
        response_json = json.loads(response_text)
        if (error := response_json['error']) != '':
            raise Qcow2TargetError(error.replace('\\n', '\n'))
        return response_json['result']


async def _list_targets() -> Mapping[str, Any]:
    # Contains dict with target names as keys and records with list of LUNs, and state indicating whether
    # there are connected initiators to the target. Each LUN contains optional disk path.
    #
    # @return: Dict with format:
    # {
    #   "<target_name: string>": {
    #     "target_id": int,
    #     "logical_units": [
    #       {"logical_unit_id": int, "file_path": "string"}
    #     ],
    #     "it_nexuses": [list of it nexus strings]
    #     "has_connections": bool
    #   }
    # }
    return await _iscsi_qcow2_request(dict(type=LIST, command={}))


async def _add_target(target_name: str) -> None:
    # Create new target if not exists. If exists - fails.
    # @param target_name: string iSCSI target name
    # @return: None
    request = dict(type=ADD_TARGET, command=dict(target_name=target_name))
    await _iscsi_qcow2_request(request)


async def _clear_target(target_name: str):
    # Detach all logical units from target.
    # @param target_name: string iSCSI target name
    # @return: list of all disk path for each lun which was attached to given target
    request = dict(
        type=CLEAR_TARGET,
        command=dict(target_name=target_name),
        )
    await _iscsi_qcow2_request(request)


async def _attach_disk_to_target(target_name: str, disk_path: str) -> int:
    # Open qcow2 disk, create logical unit,
    # attach logical unit to target.
    # @param disk_path: path to the qcow2 disk,
    #  MUST be inside to iSCSI disks root
    #  (the path can be absolute or relative to iSCSI root)
    # @param target_name: string iSCSI target name
    # @return: logical unit id of newly attached lun
    request = dict(
        type=ATTACH,
        command=dict(disk_path=disk_path, target_name=target_name),
        )
    response = await _iscsi_qcow2_request(request)
    return response['lun_id']


class IscsiTarget:

    def __init__(self, name: str):
        self._name = name

    async def _is_online(self) -> bool:
        response = await _list_targets()
        if self._name in response:
            target = response[self._name]
            logging.debug(
                "Successfully fetched target %s, online: %r, nexuses: %s",
                self._name,
                target['has_connections'],
                target['it_nexuses'],
                )
            return target['has_connections']
        raise TargetNotExist(f"Target {self._name} does not exist")

    async def wait_disconnected(self):
        wait_timeout = 60
        poll_rate = 0.5
        timeout_at = time.monotonic() + wait_timeout
        while time.monotonic() <= timeout_at:
            if not await self._is_online():
                return
            await asyncio.sleep(poll_rate)
        raise TimeoutError(
            f"Waiting timeout expired: {wait_timeout} "
            f"while waiting for target {self._name} session disconnecting")

    async def detach_block_device(self):
        try:
            await _clear_target(self._name)
        except Qcow2TargetError as err:
            if 'target does not exist' in str(err):
                raise TargetNotExist(f"Target {self._name} does not exist")
            raise

    async def create(self):
        await _add_target(self._name)

    async def attach_block_device(self, disk_path: Path):
        try:
            await _attach_disk_to_target(self._name, str(disk_path))
        except Qcow2TargetError as err:
            if 'target does not exist' in str(err):
                raise TargetNotExist(f"Target {self._name} does not exist")
            raise

    def __repr__(self):
        return f'<Target {self._name}>'


class TargetNotExist(Exception):
    pass
