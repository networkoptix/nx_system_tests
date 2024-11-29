# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import re
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Collection
from typing import Iterable
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Sequence
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.request import Request
from urllib.request import urlopen


class GitlabError(Exception):
    pass


class GitlabNotFound(GitlabError):
    pass


class GitlabForbidden(GitlabError):
    pass


_token_files = {
    'dev/nx': Path('~/.config/.secrets/gitlab_project_token_dev_nx.txt').expanduser(),
    'ft/ft': Path('~/.config/.secrets/gitlab_project_token_ft_ft.txt').expanduser(),
    'dev/cloud_portal': Path('~/.config/.secrets/gitlab_project_token_dev_cloud_portal.txt').expanduser(),
    }


class GitlabProject:

    def __init__(self, root_url, project_name):
        self._root_url = root_url
        self._project_name = project_name
        self._commit_cache = _CommitCache()

    def __repr__(self):
        return f'{self.__class__.__name__}({self._root_url!r}, {self._project_name!r})'

    def ui_url(self):
        return self._root_url + '/' + self._project_name

    def _get(self, endpoint, *args, params=None) -> bytes:
        url = self._url(endpoint, *args)
        if params:
            query = urlencode(params)
            url = url + '?' + query
        request = Request(url, headers={'PRIVATE-TOKEN': self._token()})
        try:
            with urlopen(request, timeout=10) as response:
                data = response.read()
        except HTTPError as e:
            if e.code == 404:
                raise GitlabNotFound(f"{request.full_url} not found")
            elif e.code == 403:
                raise GitlabForbidden(f"{request.full_url} forbidden")
            raise
        except URLError as e:
            raise GitlabError(e)
        except TimeoutError as e:
            raise GitlabError(e)
        return data

    def _post(self, endpoint, *args, data=None):
        if data is not None:
            data = json.dumps(data).encode('utf8')
        else:
            data = b''
        request = Request(
            self._url(endpoint, *args),
            method='POST',
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Content-Length': str(len(data)),
                'PRIVATE-TOKEN': self._token(),
                },
            )
        try:
            with urlopen(request, timeout=10) as response:
                response.read()
        except HTTPError as e:
            if e.code == 404:
                raise GitlabNotFound(f"{request.full_url} not found")
            elif e.code == 403:
                raise GitlabForbidden(f"{request.full_url} forbidden")
            raise
        except URLError as e:
            raise GitlabError(e)
        except TimeoutError as e:
            raise GitlabError(e)

    def _url(self, path, *args):
        path = re.sub(r'(?<=/):id(?=/|$)', quote_plus(self._project_name), path, 1)
        for arg in args:
            path = re.sub(r'(?<=/):\w+(?=/|$)', quote_plus(arg), path, 1)
        url = f'{self._root_url}/{path}'
        return url

    @lru_cache()
    def _token(self):
        try:
            token_path = _token_files[self._project_name]
        except KeyError:
            raise GitlabError(f"{self}: Don't know file with private token")
        try:
            return _token_files[self._project_name].read_text().strip()
        except FileNotFoundError:
            raise GitlabError(f"{self}: No private token file: {token_path}")

    def get_many_sha(self, refs) -> Collection[str]:
        result = set()
        errors = set()
        for ref in refs:
            commit = self.get_commit(ref)
            if commit is not None:
                result.add(commit.full_sha())
            else:
                errors.add(ref)
        if errors:
            raise GitlabNotFound(f"{self}: Cannot find: {' '.join(errors)}")
        return result

    def get_commit(self, commit: str) -> 'Optional[GitlabCommit]':
        try:
            return self._commit_cache.get(commit)
        except _CommitCacheMiss:
            pass
        try:
            data = self._get(
                'api/v4/projects/:id/repository/commits/:sha',
                commit,
                )
        except GitlabNotFound:
            return None
        data = json.loads(data)
        commit_object = _PlainGitlabCommit(self, data)
        self._commit_cache.add(commit_object)
        return commit_object

    def iter_recent_commits(self) -> 'Iterable[GitlabCommit]':
        yield from self._iter_recent_merge_request()
        yield from self._iter_commit_history()

    def _iter_recent_merge_request(self) -> 'Iterable[_GitlabMergeRequestCommit]':
        for page in range(1, 6):
            merge_requests = self._get(
                'api/v4/projects/:id/merge_requests',
                params={'state': 'opened', 'per_page': 100, 'page': page},
                )
            merge_requests = json.loads(merge_requests)
            if not merge_requests:
                break
            for data in merge_requests:
                commit = _GitlabMergeRequestCommit(self, data)
                if not commit.is_empty_merge_request():
                    yield commit

    def _iter_commit_history(self) -> 'Iterable[GitlabCommit]':
        for page in range(1, 21):
            commit_data = self._get(
                'api/v4/projects/:id/repository/commits',
                params={'all': 'true', 'per_page': 100, 'page': page})
            commit_data = json.loads(commit_data)
            if not commit_data:
                break
            for data in commit_data:
                yield _PlainGitlabCommit(self, data)

    def get_full_sha(self, short_sha: str) -> str:
        commit_data = self._get(
            'api/v4/projects/:id/repository/commits/:sha',
            short_sha,
            )
        commit_data = json.loads(commit_data)
        return commit_data['id']

    def retry_job(self, job_id: int):
        self._post('api/v4/projects/:id/jobs/:job_id/retry', str(job_id))

    def list_recently_failed_pipelines(self) -> Sequence['Pipeline']:
        update_after = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=1)
        merge_request_pipelines = self._get(
            'api/v4/projects/:id/pipelines/',
            params={
                'all': 'true',
                'per_page': 100,
                'status': 'failed',
                'source': 'merge_request_event',
                'order_by': 'updated_at',
                'sort': 'desc',
                'updated_after': update_after.isoformat(timespec='microseconds'),
                },
            )
        post_merge_failed_pipelines = self._get(
            'api/v4/projects/:id/pipelines/',
            params={
                'all': 'true',
                'per_page': 100,
                'status': 'failed',
                'source': 'push',
                'order_by': 'updated_at',
                'sort': 'desc',
                'updated_after': update_after.isoformat(timespec='microseconds'),
                },
            )
        # Pipeline with manual tasks is always in manual state
        post_merge_manual_pipelines = self._get(
            'api/v4/projects/:id/pipelines/',
            params={
                'all': 'true',
                'per_page': 100,
                'status': 'manual',
                'source': 'push',
                'order_by': 'updated_at',
                'sort': 'desc',
                'updated_after': update_after.isoformat(timespec='microseconds'),
                },
            )
        pipelines_raw = [
            *json.loads(merge_request_pipelines),
            *json.loads(post_merge_failed_pipelines),
            *json.loads(post_merge_manual_pipelines),
            ]
        return [Pipeline(self, api_data) for api_data in pipelines_raw]

    def list_recently_succeeded_pipelines(self, branch: str):
        # Pipeline with manual tasks is always in manual state
        status = 'manual' if branch == 'master' else 'success'
        pipelines_raw = self._get(
            'api/v4/projects/:id/pipelines/',
            params={
                'all': 'true',
                'per_page': 100,
                'status': status,
                'ref': branch,
                'order_by': 'updated_at',
                'sort': 'desc',
                },
            )
        return [Pipeline(self, api_data) for api_data in json.loads(pipelines_raw)]

    def list_pipeline_jobs(self, pipeline_id: int) -> Collection['PipelineJob']:
        response = self._get(
            'api/v4/projects/:id/pipelines/:pipeline_id/jobs',
            str(pipeline_id),
            params={'all': 'true', 'per_page': 100, 'include_retried': True},
            )
        return [PipelineJob(self, api_data) for api_data in json.loads(response)]

    def name(self) -> str:
        return self._project_name


class GitlabCommit(metaclass=ABCMeta):

    def __init__(self, project: GitlabProject, api_data):
        self._project = project
        self._data = api_data

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'{self._project!r}, '
            f'{self._data!r})')

    def url(self):
        return f'{self._project.ui_url()}/-/commits/{self.full_sha()}'

    def text(self) -> str:
        return 'SHA ' + self.full_sha()

    @abstractmethod
    def full_sha(self) -> str:
        pass

    def icon_url(self):
        return urljoin(self._project.ui_url(), '/favicon.ico')

    def committed_date(self) -> datetime:
        return datetime.fromisoformat(self._data['committed_date'])


class _PlainGitlabCommit(GitlabCommit):

    def full_sha(self):
        return self._data['id']

    def text(self) -> str:
        return f"{self._data['short_id']} {self._data['title']}"


class _GitlabMergeRequestCommit(GitlabCommit):

    def full_sha(self):
        if self.is_empty_merge_request():
            raise ValueError(f"Cannot get SHA: empty merge request: {self!r}")
        return self._data['sha']

    def is_empty_merge_request(self):
        return self._data['sha'] is None

    def text(self) -> str:
        return f"!{self._data['iid']} {self._data['title']}"


class Pipeline:

    def __init__(self, project: GitlabProject, api_data):
        self._project = project
        self._data = api_data

    def __repr__(self):
        return f"<{self.__class__.__name__} url={self._data['web_url']} sha={self._data['sha']}>"

    def list_jobs(self) -> Collection['PipelineJob']:
        return self._project.list_pipeline_jobs(self._data['id'])

    def sha(self):
        return self._data['sha']

    def list_job_attempts(self) -> Mapping[str, Sequence['PipelineJob']]:
        job_attempts = {}
        for job in self.list_jobs():
            job_attempts.setdefault(job.name(), []).append(job)
        for attempts in job_attempts.values():
            attempts.sort(key=lambda j: j.created_at())
        return job_attempts


class PipelineJob:

    def __init__(self, project: GitlabProject, api_data):
        self._project = project
        self._data = api_data

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"id={self._data['id']} "
            f"name={self._data['name']!r} "
            f"status={self._data['status']}>"
            )

    def retry(self):
        self._project.retry_job(self._data['id'])

    def name(self):
        return self._data['name']

    def stage(self):
        return self._data['stage']

    def status(self):
        return self._data['status']

    def created_at(self):
        return datetime.fromisoformat(self._data['created_at'])

    def url(self):
        return self._data['web_url']

    def pipeline_url(self):
        return self._data['pipeline']['web_url']


class _CommitCache:
    """Stores commits by SHA and its prefixes. No branches and tags.

    Refs (branches, tags etc.) are never cached.
    I.e. "master" or "stable" always raise a cache miss in return.
    """

    def __init__(self):
        self._store: MutableMapping[str, Any] = {}

    def add(self, commit_object):
        """Add prefixes of SHA to cache."""
        sha = commit_object.full_sha()
        sha = sha.lower()
        while True:  # Post-condition loop: at least one SHA must be added.
            self._store[sha] = commit_object
            sha = sha[:-1]
            if len(sha) < 8:
                return

    def get(self, sha):
        sha = sha.lower()
        try:
            return self._store[sha]
        except KeyError:
            raise _CommitCacheMiss()


class _CommitCacheMiss(Exception):
    pass


_logger = logging.getLogger(__name__)
