# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from pathlib import Path
from typing import Optional

from infrastructure._task import SerializedTask
from infrastructure._task import TaskInput
from infrastructure.gitlab_job_requester._runner import GitlabRunner

_logger = logging.getLogger(__name__)
_root = Path(__file__).parent.parent.parent
assert str(_root) in sys.path
_script_launcher_path = _root.joinpath('run_from_git.py')
if not _script_launcher_path.exists():
    raise RuntimeError(f"Required file {_script_launcher_path} does not exist")
_sync_script_path = _root.joinpath('infrastructure/git_mirror/sync.py')
if not _sync_script_path.exists():
    raise RuntimeError(f"Required file {_sync_script_path} does not exist")


class GitlabJobInput(TaskInput):

    def __init__(self, runner: GitlabRunner, fetch_uri: str):
        self._runner = runner
        self._fetch_url = fetch_uri

    def __repr__(self):
        return f'<{self.__class__.__name__} for {self._runner!r}>'

    def request_new_task(self) -> 'Optional[SerializedTask]':
        job, job_state = self._runner.request_new_job()
        if job is None:
            return
        _logger.info("Received job %r", job)
        project = job.project()
        if project == 'ft/ft':
            commit = job.sha()
        elif project == 'dev/nx':
            commit = 'master'
        elif project == 'dev/cloud_portal':
            if job.script().startswith('web_admin_tests'):
                commit = 'master'
            else:
                commit = 'stable'
        else:
            job_state.add_output(b"Job was taken by FT runner by mistake. See #ask-ft for help.\n")
            job_state.set_failure()
            return None
        env = {
            **job.env(),
            'FT_JOB_ID': str(job.id()),
            'FT_JOB_SOURCE': 'GitLab',
            'FT_JOB_API_V4_URL': job.url(),
            'FT_JOB_TOKEN': job.token(),
            'FT_JOB_PROJECT': job.project(),
            }
        if job.script() == 'sync-git-mirror':
            return {
                'args': ['python3', '-'],
                'env': env,
                'script': _sync_script_path.read_text(),
                }
        else:
            return {
                'args': ['python3', '-', self._fetch_url, commit, 'run_gitlab_job.py', job.script()],
                'env': env,
                'script': _script_launcher_path.read_text(),
                }
