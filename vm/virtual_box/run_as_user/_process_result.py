# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import NamedTuple


class ProcessResult(NamedTuple):
    exit_code: int
    stdout: bytes
    stderr: bytes
    command: str
