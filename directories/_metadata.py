# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import os
import socket
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Union

from directories._create_time import create_time


@lru_cache()
def run_metadata():
    return {
        'run_username': getpass.getuser(),
        'run_hostname': socket.gethostname(),
        'run_ft_revision': os.getenv('FT_COMMIT') or _git_current_sha(),
        'run_started_at_iso': create_time().isoformat(timespec='microseconds'),
        'run_pid': str(os.getpid()),
        'run_machinery': os.getenv('RUN_MACHINERY'),
        }


def standardize_module_name(path: Union[Path, str]) -> str:
    if not str(path).endswith('.py'):
        raise RuntimeError(f"Path must be a .py file, not {path!r}")
    script_name = standardize_script_name(path)
    return '.'.join(Path(script_name).with_suffix('').parts)


def standardize_script_name(path: Union[Path, str]) -> str:
    """Produce the same script name, whatever way the script in launched.

    When started with "tests/test_foo.py", it goes to sys.argv[0] verbatim.
    When started with "-m tests.test_foo", sys.argv[0] is absolute path.
    """
    path = Path.cwd() / path
    path = path.relative_to(_root)
    path = path.as_posix()
    return path


@lru_cache()
def _git_current_sha():
    outcome = subprocess.run(
        [
            'git',
            '-c', 'core.safecrlf=false',  # Suppress newline warnings.
            'log', '-1', '--format=format:%H',
            'HEAD',
            ],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        )
    if outcome.returncode == 0:
        return outcome.stdout.strip().decode()
    else:
        return 'error: ' + outcome.stderr.strip().decode()


_root = Path(__file__).parent.parent
assert str(_root) in sys.path
