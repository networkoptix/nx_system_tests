# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class Buffer:

    def __init__(self, batch_size: int):
        self._buffer = bytearray()
        self._count = 0
        self._batch_size = batch_size

    def append(self, item: bytes) -> None:
        self._buffer.extend(item)
        self._count += 1

    def too_much(self) -> bool:
        return self._count >= self._batch_size

    def read_out(self) -> bytes:
        r = self._buffer
        self._buffer = bytearray()
        self._count = 0
        return r
