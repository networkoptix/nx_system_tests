# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import shlex
import subprocess
from pathlib import Path

from config import global_config
from provisioning import InstallCommon
from provisioning._core import CompositeCommand
from provisioning._core import Run


class FetchRepo(CompositeCommand):

    def __init__(self, ssh_user: str, repo_dir: str):
        # In theory, any commit can be used to check out code on the remote
        # machine. Although it may be confusing to have different commits in
        # the code that does deployment and the code that is deployed. The
        # confusion may arise from the fact that all the code reside in the
        # same repo.
        repo_uri = shlex.quote(global_config['ft_fetch_origin_uri'])
        sha = shlex.quote(self._get_commit())
        user = shlex.quote(ssh_user)
        super().__init__([
            Run(f'sudo -Hu {user} mkdir -p {repo_dir}'),
            Run(f'sudo -Hu {user} git init -q {repo_dir}'),
            Run(f'sudo -Hu {user} git -C {repo_dir} config remote.origin.url {repo_uri}'),
            Run(f'sudo -Hu {user} git -C {repo_dir} config --replace remote.origin.fetch ""'),
            Run(f'sudo -Hu {user} git -C {repo_dir} fetch -q --depth 2 origin {sha}'),
            Run(f'sudo -Hu {user} git -C {repo_dir} checkout -q FETCH_HEAD'),
            ])
        self._repr = f'{FetchRepo.__name__}({ssh_user!r}, {repo_dir!r})'

    @staticmethod
    def _get_commit():
        rev_parse = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True)
        rev_parse.check_returncode()
        return rev_parse.stdout.decode().strip()

    def __repr__(self):
        return self._repr


class LaunchSimpleSystemdService(CompositeCommand):

    def __init__(self, ssh_user: str, unit_file: Path):
        super().__init__([
            UploadSystemdFile(ssh_user, unit_file),
            SystemCtl(ssh_user, 'daemon-reload'),
            SystemCtl(ssh_user, 'enable', unit_file.name),
            SystemCtl(ssh_user, 'restart', unit_file.name),
            SystemCtl(ssh_user, 'status', unit_file.name),
            ])
        self._repr = f'{LaunchSimpleSystemdService.__name__}({ssh_user!r}, {unit_file!r})'

    def __repr__(self):
        return self._repr


class UploadSystemdFile(InstallCommon):

    def __init__(self, ssh_user: str, source_service_path: Path):
        super().__init__(ssh_user, str(source_service_path), f'~{ssh_user}/.config/systemd/user/')


class SystemCtl(Run):

    def __init__(self, user: str, *command: str):
        u = shlex.quote(user)
        c = shlex.join(command)
        super().__init__(f'sudo -u {u} XDG_RUNTIME_DIR=/run/user/$(id -u {u}) systemctl --user {c}')
        self._repr = f'{SystemCtl.__name__}{(user, *command)!r}'


class PrepareVenv(Run):

    def __init__(self, ssh_user: str, root_dir: str, project_dir: str):
        user = shlex.quote(ssh_user)
        super().__init__(f'sudo -u {user} PYTHONPATH={root_dir} python3 -m make_venv -p {root_dir}/{project_dir}')
