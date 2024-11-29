# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import shlex
import stat
import subprocess
from datetime import datetime
from pathlib import Path


class FakeGitRepo:

    def __init__(self):
        repo_root = Path('~/.cache/fake_git_repo').expanduser()
        repo_root.mkdir(parents=False, exist_ok=True)
        self._repo_path = repo_root / f'{datetime.utcnow():%Y%m%d%H%M%S%f}-{os.getpid()}'
        self._repo_path.mkdir(exist_ok=True)
        os.environ.pop('GIT_DIR', None)
        os.environ.pop('GIT_WORK_TREE', None)
        os.environ.pop('GIT_INDEX_FILE', None)
        subprocess.run(['git', 'init', '-q'], check=True, cwd=self._repo_path)
        subprocess.run(['git', 'config', 'user.email', shlex.quote('ft@example.com')], check=True, cwd=self._repo_path)
        subprocess.run(['git', 'config', 'user.name', shlex.quote('FT Unittest')], check=True, cwd=self._repo_path)

    def add_file_to_stable(self, file_name: str, content: str):
        file_path = self._repo_path / file_name
        file_path.write_text(content)
        subprocess.run(['git', 'add', '.'], check=True, cwd=self._repo_path)
        subprocess.run(['git', 'commit', '-qam', 'some-commit'], cwd=self._repo_path)
        subprocess.run(['git', 'tag', 'stable', '-f'], cwd=self._repo_path, check=True)

    def uri(self):
        return self._repo_path.joinpath('.git').as_posix()

    def delete(self):
        paths = [self._repo_path]
        git_folder = self._repo_path / '.git'
        while paths:
            current_path = paths.pop()
            if current_path == git_folder or git_folder in current_path.parents:
                # Git creates some files with read-only permissions.
                # Set full user permissions to delete them.
                current_path.chmod(stat.S_IRWXU)
            if current_path.is_dir():
                children = list(current_path.iterdir())
                if children:
                    paths.extend([current_path, *children])
                else:
                    current_path.rmdir()
            else:
                current_path.unlink()
        if self._repo_path.exists():
            raise RuntimeError(f"Failed to delete local git repository {self._repo_path}")
