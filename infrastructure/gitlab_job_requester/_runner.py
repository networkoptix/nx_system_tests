# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Mapping
from typing import Tuple
from typing import Union
from urllib.parse import urlparse

from infrastructure.gitlab_api import GitLabConnection
from infrastructure.gitlab_api import GitLabJSONRequest
from infrastructure.gitlab_api import GitlabJobState

_logger = logging.getLogger(__name__)


class GitlabRunner:

    def __init__(self, url: str, auth_token_path: str):
        self._conn = GitLabConnection(url)
        self._token_path_raw = auth_token_path
        self._token = Path(auth_token_path).expanduser().read_text().rstrip('\n')
        self._id = self._get_runner_id()

    def __repr__(self):
        return f'<GitlabRunner {self._conn!r}, {self._token_path_raw!r}, {self._id!r}>'

    def request_new_job(self) -> Union[Tuple['GitlabJob', 'GitlabJobState'], Tuple[None, None]]:
        response = self._conn.request(GitLabJSONRequest('POST', '/api/v4/jobs/request', {
            'token': self._token,
            'info': {'features': {'refspecs': True}},
            }))
        if response.status() == 204:
            return None, None
        if response.status() == 201:
            job = GitlabJob(response.json())
            job_state = GitlabJobState(self._conn, job.url(), job.token())
            message = (
                f"Job is taken by FT runner (runner id {self._id}). "
                "See #ask-ft channel for help.\n")
            job_state.add_output(message.encode('utf8'))
            return job, job_state
        raise RuntimeError(f'HTTP {response.status()}: {response.raw()!r}')

    def _get_runner_id(self) -> str:
        request = GitLabJSONRequest('POST', '/api/v4/runners/verify', {'token': self._token})
        response = self._conn.request(request)
        if response.status() == 403:
            raise RuntimeError(f"Runner token in file {self._token_path_raw!r} is not valid")
        if response.status() >= 400:
            raise RuntimeError(f'HTTP {response.status()}: {response.raw()!r}')
        return str(response.json()['id'])


class GitlabJob:

    def __init__(self, job_raw):
        self._data = job_raw

    def __repr__(self):
        return f'<{self.__class__.__name__} id={self.id()} sha={self.sha()}>'

    def sha(self) -> str:
        return self._data['git_info']['sha']

    def script(self) -> str:
        return self._data['steps'][0]['script'][0]

    def _base_url(self) -> str:
        return self._variable('CI_API_V4_URL')

    def token(self):
        return self._data['token']

    def id(self) -> int:
        return self._data['id']

    def _variable(self, key):
        for v in self._data['variables']:
            if v['key'] == key:
                return v['value']
        raise RuntimeError("%r: Variable not found: %r", self, key)

    def env(self) -> Mapping[str, str]:
        env = {}
        try:
            env_whitelist = Path(__file__).with_name('env_whitelist.txt').read_text().splitlines()
        except FileNotFoundError:
            env_whitelist = ['*']
        banned_keys = []
        for variable in self._data['variables']:
            if not any(fnmatch(variable['key'], mask) for mask in env_whitelist):
                banned_keys.append(variable['key'])
                continue
            if variable['value'] is None:
                _logger.debug("None value cannot be in env; skip")
                continue
            if not isinstance(variable['key'], str):
                _logger.debug(
                    "Key %s (type=%s) is not a string and cannot be in env; cast to string",
                    variable['key'], type(variable['key']))
            if not isinstance(variable['value'], str):
                _logger.debug(
                    "Value %s (type=%s) is not a string and cannot be in env; cast to string",
                    variable['value'], type(variable['value']))
            env[str(variable['key'])] = str(variable['value'])
        if banned_keys:
            _logger.debug("Variables %s are not in whitelist %s", banned_keys, env_whitelist)
        return env

    @lru_cache(1)
    def project(self):
        parsed = urlparse(self._data['git_info']['repo_url'])
        project = parsed.path.lstrip('/')
        if project.endswith('.git'):
            return project[:-4]
        return project

    def url(self):
        return self._base_url() + f'/jobs/{self.id()}'
