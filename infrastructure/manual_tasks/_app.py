# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import re
from abc import abstractmethod
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlencode

from config import global_config
from infrastructure._http import App
from infrastructure._http import HTTPMethod
from infrastructure._http import MethodHandler
from infrastructure._message_broker_config import get_default_client


def make_app():
    return partial(App, handlers=[
        ShowForm(),
        RunTests(),
        CreateVMSSnapshot(),
        CreateBaseSnapshot(),
        ])


class ShowForm(MethodHandler):
    _path = '/'
    _method = HTTPMethod.GET

    def __init__(self):
        self._form = Path(__file__).with_name('form.html').read_bytes()

    def _handle(self, request: BaseHTTPRequestHandler):
        request.send_response(HTTPStatus.OK.value)
        request.send_header('Content-Length', str(len(self._form)))
        request.end_headers()
        request.wfile.write(self._form)


class _RunTask(MethodHandler):
    _method = HTTPMethod.POST

    def __init__(self, task_group):
        self._task_group = task_group
        self._tasks_counter = 0

    def _handle(self, request: BaseHTTPRequestHandler):
        self._tasks_counter = 0
        payload = _parse_form_data(_get_form(request))
        try:
            url = self._run_manual_task(payload)
        except _InvalidArguments as e:
            request.send_error(HTTPStatus.BAD_REQUEST.value, str(e))
            return
        request.send_response(HTTPStatus.SEE_OTHER.value)
        request.send_header('Location', url)
        request.end_headers()

    @abstractmethod
    def _run_manual_task(self, payload):
        pass

    def _create_message(self, args_list, env_variables):
        self._tasks_counter += 1
        job_id = f'{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{self._tasks_counter}'
        message = {
            'script': self._get_script_launcher(),
            'args': [
                'python3',
                '-',
                global_config['ft_fetch_uri'],
                *args_list,
                ],
            'env': {
                'FT_JOB_ID': job_id,
                'FT_JOB_SOURCE': 'Manual',
                **env_variables,
                },
            }
        self._message_output().write_message(json.dumps(message))

    def _message_output(self):
        return get_default_client().get_producer(self._task_group)

    @lru_cache(1)
    def _get_script_launcher(self):
        return Path('run_from_git.py').resolve().read_text()


class RunTests(_RunTask):
    _path = '/run'

    def __init__(self):
        super().__init__('ft:tasks_batch_run')

    def _run_manual_task(self, payload):
        installers_url = payload.get('distrib_url')
        if installers_url is not None:
            if not installers_url.startswith('https://'):
                raise _InvalidArguments("Distrib URL must start with https://")
            if not installers_url.endswith('/distrib/'):
                raise _InvalidArguments("Distrib URL must end with /distrib/")
        [test_file, _sep, test] = payload['test_id'].partition('::')
        if not test_file.endswith('.py'):
            raise _InvalidArguments("Invalid test file name, must be a path to Python script")
        test_module = re.sub(r'\.py$', '', test_file).replace('/', '.')
        test_args = ['-m', test_module, test] if test else ['-m', test_module]
        cloud_host = payload.get('cloud_host')
        count = min(100, int(payload.get('count', 1)))
        for _ in range(count):
            self._create_message(
                args_list=[
                    payload.get('ft_commit', 'master'),
                    '-m', 'make_venv',
                    *test_args,
                    *(['--installers-url', installers_url] if installers_url else []),
                    *(['--test-cloud-host', cloud_host] if cloud_host else []),
                    ],
                env_variables={
                    'BATCH_JOB_RUN_ID': datetime.utcnow().strftime('%Y%m%d%H%M%S%f'),
                    'BATCH_JOB_STAGE': test,
                    },
                )

        params = {}
        if test and not test_module.endswith(f'.{test}'):
            params['args'] = ' '.join(['-m', test_module, test])
        else:
            params['args'] = ' '.join(['-m', test_module])
        if installers_url is not None:
            params['run_vms_url'] = installers_url
        return 'https://us.nxft.dev/runs/?' + urlencode(params)


class CreateVMSSnapshot(_RunTask):
    _path = '/vms-snapshot'

    def __init__(self):
        super().__init__('ft:tasks_snapshot_vbox')

    def _run_manual_task(self, payload):
        installers_url = payload['distrib_url']
        if not installers_url.startswith('https://'):
            raise _InvalidArguments("Distrib URL must start with https://")
        if not installers_url.endswith('/distrib/'):
            raise _InvalidArguments("Distrib URL must end with /distrib/")
        component = payload['component']
        if component not in {'mediaserver', 'client', 'bundle'}:
            raise _InvalidArguments(f"Unknown component: {component}")
        os_name = payload['os_name']
        known_os_names = [
            'ubuntu18',
            'ubuntu20',
            'ubuntu22',
            'ubuntu24',
            'win10',
            'win11',
            'win2019',
            ]
        if os_name not in known_os_names:
            raise _InvalidArguments(f"Unknown OS name: {os_name}")
        self._create_message(
            args_list=[
                payload.get('branch', 'master'),
                '-m', 'make_venv',
                '-m', f'vm.nxwitness_snapshots.{component}_plugin',
                '--installers-url', installers_url,
                '--os-name', os_name,
                ],
            env_variables={},
            )
        params = {
            'group': self._task_group,
            'source': 'Manual',
            }
        return 'http://sc-ft003:8050/tasks/?' + urlencode(params)


class CreateBaseSnapshot(_RunTask):
    _path = '/base-snapshot'

    def __init__(self):
        super().__init__('ft:tasks_snapshot_vbox_base')

    def _run_manual_task(self, payload):
        os_name = payload['os_name']
        known_os_names = [
            'ubuntu18',
            'ubuntu20',
            'ubuntu22',
            'ubuntu24',
            'chrome',
            'openldap',
            'win10',
            'win11',
            'win2019',
            'active_directory',
            ]
        if os_name not in known_os_names:
            raise _InvalidArguments(f"Unknown OS name: {os_name}")
        self._create_message(
            args_list=[
                payload.get('branch', 'master'),
                'make_venv.py',
                '-m',
                'vm.virtual_box.configuration.build_base_snapshot',
                os_name,
                ],
            env_variables={},
            )
        return 'http://sc-ft003:8050/tasks/?' + urlencode([('group', self._task_group)])


def _get_form(request):
    content_length = int(request.headers['Content-Length'])
    content = request.rfile.read(content_length).decode()
    _logger.info("Request: %r", content[:1024])
    return parse_qs(content)


def _parse_form_data(form):
    return {key: value[0] for key, value in form.items() if value}


class _InvalidArguments(Exception):
    pass


_logger = logging.getLogger()
