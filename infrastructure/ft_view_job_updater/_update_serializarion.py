# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import shlex

from infrastructure._task_update import PermanentReportError


def ft_view_update_serialize(message_bytes):
    try:
        message_raw = json.loads(message_bytes)
    except ValueError as e:
        raise PermanentReportError(f'json.loads(): {e}')
    try:
        exe = ['python']
        args = message_raw['args'][4:]
        if args[:2] == ['-m', 'make_venv']:
            exe = [*exe, *args[:2]]
            args = args[2:]
        options = {}
        for i in reversed(range(len(args))):
            if args[i].startswith('--'):
                option = args.pop(i)
                [name, _, value] = option.partition('=')
                options['opt.' + name] = value  # Empty value possible.
        return {
            'cmdline': {
                'env.COMMIT': message_raw['env']['BATCH_JOB_REVISION'],
                'env.MACHINERY': message_raw['env']['RUN_MACHINERY'],
                'exe': shlex.join(exe),
                'args': shlex.join(args),
                **options,
                },
            'revision': message_raw['env']['BATCH_JOB_REVISION'],
            'stage': message_raw['env']['BATCH_JOB_STAGE'],
            'vms': message_raw['env']['BATCH_JOB_VMS'],
            'machinery': message_raw['env']['RUN_MACHINERY'],
            'job_run_id': message_raw['env']['BATCH_JOB_RUN_ID'],
            'task_artifacts_url': message_raw.get('task_artifacts_url'),
            'status': message_raw.get('status'),
            }
    except KeyError as e:
        raise PermanentReportError(f"Missing key: {e}")
