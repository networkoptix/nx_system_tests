# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import shlex
import subprocess
from typing import Sequence

from vm.virtual_box.run_as_user._process_result import ProcessResult


def run_as_local_user(user: str, args: Sequence[str]) -> ProcessResult:
    timeout_sec = 60
    user_command = ['sudo', '-Hu', user, *args]
    try:
        result = subprocess.run(user_command, capture_output=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command {args} did not finish in {timeout_sec:.1f} seconds")
    return ProcessResult(result.returncode, result.stdout, result.stderr, shlex.join(user_command))
