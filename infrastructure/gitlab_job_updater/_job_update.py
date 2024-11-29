# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from collections import OrderedDict
from typing import Tuple
from urllib.parse import urlsplit

from infrastructure._task_update import PermanentReportError
from infrastructure._task_update import TemporaryReportError
from infrastructure._task_update import UpdateReportFactory
from infrastructure.gitlab_api import GitLabConnection
from infrastructure.gitlab_api import GitlabJobNotRunning
from infrastructure.gitlab_api import GitlabJobState
from infrastructure.gitlab_api import GitlabRunnerError
from infrastructure.gitlab_api import GitlabStateTransitionError


class GitlabJobReportFactory(UpdateReportFactory):
    """Pool of job state objects, which must persist across requests."""

    def __init__(self, base_url: str):
        self._store: OrderedDict[Tuple[str, str], GitlabJobState] = OrderedDict({})
        self._conn = GitLabConnection(base_url)

    def send_report(self, update_bytes):
        try:
            update_raw = json.loads(update_bytes)
        except ValueError as e:
            raise PermanentReportError(f'json.loads(): {e}')
        try:
            job_url = update_raw['env']['FT_JOB_API_V4_URL']
            token = update_raw['env']['FT_JOB_TOKEN']
        except KeyError as e:
            raise PermanentReportError(f"Missing key: {e}")
        try:
            state = self._store[job_url, token]
        except KeyError:
            url_path = urlsplit(job_url).path
            state = GitlabJobState(self._conn, url_path, token)
            self._store[job_url, token] = state
            if len(self._store) > 20000:
                self._store.popitem(last=False)
        output = ''
        for key in 'status', 'worker_id', 'task_artifacts_url':
            if key in update_raw:
                output += key + '=' + update_raw[key] + '\n'
        if 'output' in update_raw:
            output += update_raw['output'] + '\n'
        try:
            if output:
                state.add_output(output.encode())
            if update_raw.get('failed', False):
                state.set_failure()
            elif update_raw.get('succeed', False):
                state.set_success()
        except GitlabStateTransitionError as e:
            raise PermanentReportError(f"{update_raw}: State transition error: {e}")
        except GitlabJobNotRunning:
            raise PermanentReportError(f"{update_raw}: Not in running state")
        except GitlabRunnerError as e:
            raise TemporaryReportError(f"{update_raw}: Failed to send trace: {e}")


_logger = logging.getLogger(__name__)
