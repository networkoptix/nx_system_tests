# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from infrastructure.gitlab_api._connection import GitLabConnection
from infrastructure.gitlab_api._connection import GitLabGenericRequest
from infrastructure.gitlab_api._connection import GitLabJSONRequest


class GitlabJobState:

    def __init__(self, conn: GitLabConnection, job_url: str, job_token: str):
        self._conn = conn
        self._url = job_url.rstrip('/')
        self._job_token = job_token
        self._trace = _GitlabJobTrace(conn, job_url, job_token)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._url}"

    def add_output(self, output: bytes):
        self._trace.add(output)

    def set_success(self):
        self._set('success')

    def set_failure(self):
        self._set('failed')

    def _set(self, state: str):
        _logger.debug("%r: Set state %r", self, state)
        data = {
            'token': self._job_token,
            'state': state,
            'failure_reason': 'script_failure',
            }
        request = GitLabJSONRequest('PUT', self._url, data)
        response = self._conn.request(request)
        if response.status() == 400 and response.raw() == b'400':
            raise GitlabStateTransitionError()
        if response.status() >= 400:
            raise GitlabRunnerError(f'HTTP {response.status()}: {response.raw()}')
        if response.status() == 200:
            return
        raise _GitlabUnexpectedStatus(response.status(), response.raw())


class _GitlabJobTrace:
    """Persistent job output (trace) object that stores current offset.

    Along with a chunk of output, GitLab requires the offset of this chunk.
    That's why the offset is being maintained throughout job's lifecycle.
    Losing the offset is not a catastrophe though: the error contains the
    current offset known to GitLab.
    """

    def __init__(self, conn: GitLabConnection, job_url: str, job_token: str):
        self._conn = conn
        self._url = job_url.rstrip('/') + '/trace'
        self._job_token = job_token
        self._offset = 0

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._url}"

    def add(self, output: bytes):
        """Send output to the job."""
        current_offset = self._offset
        try:
            new_offset = self._send_trace(current_offset, output)
        except _InvalidOffset as e:
            # New object attempts to send output with zero offset. If some output was added
            # earlier - GitLab returns error and actual offset which is used to resend output.
            current_offset = e.offset
            new_offset = self._send_trace(current_offset, output)
        self._offset = new_offset

    def _send_trace(self, offset: int, chunk: bytes) -> int:
        """Send an API call to append data to job output.

        See: https://gitlab.com/gitlab-org/gitlab/-/blob/602a5f74b84e76860af6bf0752923a765ac8eca6/lib/api/ci/runner.rb#L223
        """
        headers = {
            'JOB-TOKEN': self._job_token,
            'Content-Range': f'{offset}-',
            }
        request = GitLabGenericRequest('PATCH', self._url, chunk, headers)
        response = self._conn.request(request)
        if response.status() == 403:
            raise GitlabJobNotRunning(response.status(), response.raw())
        if response.status() == 416:
            [_zero, offset] = response.range()
            raise _InvalidOffset(offset)
        if response.status() >= 400:
            raise GitlabRunnerError(f'HTTP {response.status()}: {response.raw()}')
        if response.status() == 202:
            # It's unclear what GitLab sends in return. It's not checked in
            # GitLab's own tests. Perhaps, it's the job update interval.
            _logger.debug("%r: Add trace %d +%d: %s", self, offset, len(chunk), chunk)
            [_zero, new_offset] = response.range()
            return new_offset
        raise _GitlabUnexpectedStatus(response.status(), response.raw())


class GitlabRunnerError(Exception):
    pass


class GitlabStateTransitionError(Exception):
    pass


class GitlabJobNotRunning(GitlabRunnerError):
    pass


class _GitlabUnexpectedStatus(Exception):

    def __init__(self, status, message):
        super().__init__(f"Unexpected HTTP {status}: {message}")


class _InvalidOffset(Exception):

    def __init__(self, offset: int):
        super().__init__(f"Proper offset {offset}")
        self.offset = offset


_logger = logging.getLogger(__name__)
