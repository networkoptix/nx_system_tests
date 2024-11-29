# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import netrc
import os
from abc import ABCMeta
from abc import abstractmethod
from base64 import b64encode
from itertools import chain
from pathlib import Path
from typing import Collection
from typing import List
from typing import Optional
from typing import Sequence
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse
from urllib.request import Request
from urllib.request import urlopen

DEFAULT_TESTRAIL_URL = os.environ.get('TESTRAIL_URL') or 'https://networkoptix.testrail.net/'


class _TestrailObject:

    def __init__(self, raw: dict, base_url: str):
        self._raw = raw
        self._base_url = base_url


class TestrailTest(_TestrailObject):

    def id(self) -> int:
        return self._raw['id']

    def serialize(self):
        return {
            'url': f'{self._base_url}index.php?/tests/view/{self.id()}',
            'name': self._raw['name'],
            }

    def case_id(self):
        return self._raw['case_id']

    def configs(self):
        return self._raw['configs']

    def __hash__(self):
        return id(self)


class TestrailProjectPhase(_TestrailObject, metaclass=ABCMeta):
    PHASE_TYPE: str

    def id(self) -> int:
        return self._raw['id']

    def name(self):
        if self._raw.get('config') is not None:
            return f"{self._raw['name']} ({self._raw['config']})"
        else:
            return self._raw['name']

    def present(self, url: Optional[str] = None):
        return {
            'phase': {
                'name': self.name(),
                'type': self.PHASE_TYPE,
                'url': url or self._raw['url'],
                },
            }

    @abstractmethod
    def list_runs(self) -> Sequence['TestrailRun']:
        pass


class TestrailRun(TestrailProjectPhase):
    PHASE_TYPE = 'Run'

    def list_tests(self) -> Collection[TestrailTest]:
        return [TestrailTest(raw, self._base_url) for raw in self._raw['tests']]

    def list_runs(self) -> Sequence['TestrailRun']:
        return [self]


class TestrailPlan(TestrailProjectPhase):
    PHASE_TYPE = 'Plan'

    def list_runs(self) -> Sequence[TestrailRun]:
        return [TestrailRun(raw, self._base_url) for raw in self._raw['runs']]


class TestrailProject(_TestrailObject):

    def present(self):
        return {
            'project': {
                'name': self._raw['name'],
                },
            }

    def list_phases(self) -> Collection[TestrailProjectPhase]:
        return sorted(
            chain(self._list_plans(), self._list_runs()),
            key=lambda obj: obj.id(),
            reverse=True,
            )

    def _list_plans(self) -> List[TestrailPlan]:
        return [TestrailPlan(raw, self._base_url) for raw in self._raw['plans']]

    def _list_runs(self) -> List[TestrailRun]:
        return [TestrailRun(raw, self._base_url) for raw in self._raw['runs']]


class _GetApi(metaclass=ABCMeta):

    @abstractmethod
    def get(self, path: str) -> dict:
        pass

    @abstractmethod
    def base_url(self):
        pass


class TestrailApi(_GetApi):

    def __init__(self, base_url):
        self._base_url = base_url
        [user, password] = self._get_credentials(base_url)
        self._credentials = b64encode(f'{user}:{password}'.encode()).decode()

    def base_url(self):
        return self._base_url

    def get(self, path):
        return self._send_request('GET', path)

    def post(self, path, data):
        self._send_request('POST', path, data=data)

    def _send_request(self, method, path, data=None):
        _logger.info("%s %r", method, path)
        url = self._make_url(path)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {self._credentials}',
            }
        request = Request(method=method, url=url, headers=headers, data=data)
        try:
            with urlopen(request) as response:
                return json.loads(response.read())
        except HTTPError as e:
            raise RuntimeError(
                f"HTTP Error {e.status} from TestRail endpoint {url}: {e.read()}")

    def _make_url(self, path: str):
        [scheme, netloc, _path, *other] = urlparse(self._base_url)
        return urlunparse((scheme, netloc, f'index.php?{path}', *other))

    @staticmethod
    def _get_credentials(base_url: str):
        host = urlparse(base_url).hostname
        netrc_db = netrc.netrc(Path('~/.config/.secrets/testrail.netrc').expanduser())
        try:
            [username, _, password] = netrc_db.authenticators(host)
        except TypeError:
            raise RuntimeError(f"Missing TestRail credentials for {host!r}")
        return username, password


class TestrailClient:

    def __init__(self, api: _GetApi):
        self._api = api

    def find_project_phase(self, phase_id: int) -> TestrailProjectPhase:
        for project in self.get_projects():
            for phase in project.list_phases():
                if phase.id() == phase_id:
                    return phase
        raise IndexError(f"No such phase with {phase_id=}")

    def get_projects(self) -> Sequence[TestrailProject]:
        projects = self._bulk_get(
            path='/api/v2/get_projects',
            array_key='projects',
            )
        results = []
        supports_autotests = ('VMS', 'Web', 'Cloud')
        for project in projects:
            if project['name'] not in supports_autotests:
                continue
            project['plans'] = self._get_plans(project['id'])
            project['runs'] = self._get_runs_by_project(project['id'])
            results.append(TestrailProject(project, self._api.base_url()))
        return results

    def get_run(self, run_id):
        run = self._api.get(f'/api/v2/get_run/{run_id}')
        return TestrailRun(self._populate_run(run), self._api.base_url())

    def _get_plans(self, project_id):
        plans = self._bulk_get(
            path=f'/api/v2/get_plans/{project_id}',
            array_key='plans',
            )
        results = []
        for plan in plans:
            if plan['is_completed']:
                continue
            plan['runs'] = self._get_runs_by_plan(plan['id'])
            results.append(plan)
        return results

    def _get_runs_by_project(self, project_id):
        runs = self._bulk_get(
            path=f'/api/v2/get_runs/{project_id}',
            array_key='runs',
            )
        return self._filter_and_populate_runs(runs)

    def _get_runs_by_plan(self, plan_id):
        plan = self._api.get(f'/api/v2/get_plan/{plan_id}')
        runs = []
        for entry in plan['entries']:
            runs.extend(entry['runs'])
        return self._filter_and_populate_runs(runs)

    def _filter_and_populate_runs(self, runs):
        results = []
        for run in runs:
            if run['is_completed']:
                continue
            self._populate_run(run)
            results.append(run)
        return results

    def _populate_run(self, run):
        run['configs'] = self._get_run_configs(run)
        run['tests'] = self._get_tests(run)
        return run

    def _get_tests(self, run):
        run_id = run['id']
        result = self._bulk_get(
            path=f'/api/v2/get_tests/{run_id}',
            array_key='tests',
            )
        for test in result:
            test['name'] = test.get('title')
            test['configs'] = run['configs']
        return result

    def _get_run_configs(self, run):
        config_ids = run['config_ids']
        if len(config_ids) == 0:
            return []
        elif len(config_ids) == 1:
            return [run['config']]
        else:
            project_configs = self._get_flatten_configs(run['project_id'])
            return [project_configs[config_id]['name'] for config_id in config_ids]

    def _get_flatten_configs(self, project_id):
        groups = self._api.get(f'/api/v2/get_configs/{project_id}')
        result = {}
        for group in groups:
            for config in group['configs']:
                result[config['id']] = {
                    'group': group['name'],
                    'project_id': project_id,
                    **config,
                    }
        return result

    def _bulk_get(self, path, array_key):
        result = []
        query_string_mapping = {'offset': 0, 'limit': 250}
        path = f'{path}&{urlencode(query_string_mapping)}'
        while True:
            response = self._api.get(path)
            result.extend(response.get(array_key, []))
            path = response['_links']['next']
            if path is None:
                return result


_logger = logging.getLogger(__name__)
