# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from typing import NamedTuple


class RequestType:
    ADD = "ADD"
    DELETE = "DELETE"


class Request(NamedTuple):
    size: int
    name: str
    type: str

    @classmethod
    def unpack(cls, data: str):
        print(data)
        return cls(**json.loads(data))

    @classmethod
    def add(cls, name: str, size: int):
        return cls(name=name, size=size, type=RequestType.ADD)

    @classmethod
    def delete(cls, name: str):
        return cls(name=name, size=0, type=RequestType.DELETE)

    def __str__(self) -> str:
        return json.dumps({'name': self.name, 'size': self.size, 'type': self.type})


class Response(NamedTuple):
    status: int
    message: str

    def __str__(self) -> str:
        return json.dumps({'message': self.message, 'status': self.status})

    @classmethod
    def unpack(cls, data: str) -> 'Response':
        return cls(**json.loads(data))

    @classmethod
    def ok(cls):
        return cls(message='Ok', status=0)

    @classmethod
    def error(cls, message: str):
        return cls(message=message, status=1)
