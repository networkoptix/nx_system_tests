# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)


def main(args):
    [repo_path, revision, script, *script_args] = args
    repo_path = Path(repo_path).expanduser()
    _logger.info("====== Prepare repository: Commit %s from %s ======", revision, repo_path)
    source_dir = Path(os.getcwd()) / 'ft'
    source_dir.mkdir(exist_ok=True, parents=False)
    source_dir.joinpath('.git').mkdir(exist_ok=True)
    git_index = '.git/index'   # relative to work-tree
    os.environ['GIT_DIR'] = str(repo_path)
    os.environ['GIT_WORK_TREE'] = str(source_dir)
    os.environ['GIT_INDEX_FILE'] = git_index
    # Lock can persist after Git process crashes or exits with error.
    # Only one process works with this index file at a time, so it can be safely removed.
    source_dir.joinpath(git_index + '.lock').unlink(missing_ok=True)
    try:
        revision = subprocess.check_output(['git', 'rev-parse', revision]).decode().strip()
        subprocess.run(['git', 'checkout', '--no-overlay', '-q', revision + '^{tree}', '--', '.'], timeout=10, check=True)
        subprocess.run(['git', 'clean', '-fd', '-q'], timeout=10, check=True)
    except subprocess.CalledProcessError:
        _logger.info("====== Prepare repository: Fail ======")
        return 10
    os.environ['FT_COMMIT'] = revision
    _logger.info("====== Prepare repository: Success ======")
    command = [sys.executable, script, *script_args]
    _logger.info("====== Running command: %s ======", shlex.join(command))
    process = subprocess.run(command, cwd=source_dir, env={'PYTHONPATH': '.', **os.environ})
    _logger.info("====== Running command: Exit code %s ======", process.returncode)
    return process.returncode


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main(sys.argv[1:]))
