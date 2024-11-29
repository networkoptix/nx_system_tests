# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from typing import Any
from typing import Mapping
from typing import NamedTuple
from typing import Sequence
from typing import TypedDict
from typing import Union


class _ServerStatus:
    OK = "OK"
    NOK = "NOK"
    ACK = "ACK"
    SRV_GREET = "GREET"
    SRV_ERR = "ERROR"
    TIMEOUT = "TIMEOUT"


class RequestType:

    UNLOCK_MACHINE = 'unlock_machine'
    GET_SNAPSHOT = "get_snapshot"
    COMMIT_SNAPSHOT = "commit_snapshot"


class LockSnapshotRequest(TypedDict, total=False):
    model: str
    arch: str
    os: str
    name: str
    disk_stems: Sequence[str]
    timeout: int


class LockedMachineClientInfo(TypedDict):
    machine_name: str
    ip_address: str
    ssh_port: int
    username: str
    ssh_key: str


class ReleaseMachineRequest(TypedDict):
    machine_name: str


class CommitSnapshotRequest(TypedDict):
    machine_name: str


RequestDataType = Union[
    LockSnapshotRequest,
    ReleaseMachineRequest,
    CommitSnapshotRequest,
    ]


class StatusMsg:

    def __init__(self, status: str, message: str, data: Mapping[str, Any]):
        self._status = status
        self._message = message
        self._data = data

    def as_bytes(self) -> bytes:
        json_struct = (self._status, self._message, self._data)
        return json.dumps(json_struct).encode('utf-8')


class Greet(StatusMsg):

    def __init__(self, message: str):
        super().__init__(status=_ServerStatus.SRV_GREET, message=message, data={})


class Ack(StatusMsg):

    def __init__(self):
        super().__init__(status=_ServerStatus.ACK, message="Request received", data={})


class Error(StatusMsg):

    def __init__(self, message: str):
        super().__init__(status=_ServerStatus.SRV_ERR, message=message, data={})


class Ok(StatusMsg):

    def __init__(self, data: Mapping[str, Union[Sequence, int, str]]):
        super().__init__(status=_ServerStatus.OK, message="Success", data=data)


class Nok(StatusMsg):

    def __init__(self, message: str):
        super().__init__(status=_ServerStatus.NOK, message=message, data={})


class Timeout(StatusMsg):

    def __init__(self, message: str):
        super().__init__(status=_ServerStatus.TIMEOUT, message=message, data={})


class RequestMsg(NamedTuple):

    type: str
    data: RequestDataType = {}

    @classmethod
    def from_bytes(cls, bytes_data: bytes):
        return cls(*json.loads(bytes_data))

    def __str__(self):
        return json.dumps(self)

    def __bytes__(self):
        return str(self).encode('utf-8')
