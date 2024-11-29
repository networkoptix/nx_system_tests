# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import shlex
import sys
from pathlib import Path
from typing import Any
from typing import Mapping


def ft_task_db_to_redis(raw: Mapping[str, Any], repo_uri: str):
    env = {
        k.removeprefix('env.'): v
        for k, v in raw['cmdline'].items()
        if k.startswith('env.')
        }
    exe = shlex.split(raw['cmdline']['exe'])
    args = shlex.split(raw['cmdline']['args'])
    optionals = [
        k.removeprefix('opt.') + '=' + v
        for k, v in raw['cmdline'].items()
        if k.startswith('opt.')
        ]
    if exe[0] != 'python':
        raise ValueError(f"Must be python command: {raw['cmdline']}")
    return {
        'args': ['python3', '-', repo_uri, env['COMMIT'], *exe[1:], *args, *optionals],
        'env': {
            'RUN_MACHINERY': env['MACHINERY'],
            'FT_JOB_ID': raw['job_run_id'],
            'FT_JOB_SOURCE': 'FTView',
            'BATCH_JOB_RUN_ID': raw['job_run_id'],
            'BATCH_JOB_REVISION': env['COMMIT'],
            'BATCH_JOB_VMS': raw['cmdline'].get('opt.--installers-url', ''),
            'BATCH_JOB_STAGE': '::'.join([args[1].replace('.', '/') + '.py', *args[2:]]),
            },
        'script': _script_launcher_path.read_text(),
        }


_root = Path(__file__).parent.parent.parent
assert str(_root) in sys.path
_script_launcher_path = _root.joinpath('run_from_git.py')
if not _script_launcher_path.exists():
    raise RuntimeError(f"Required file {_script_launcher_path} does not exist")
