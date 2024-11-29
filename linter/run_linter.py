# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import fnmatch
import logging
import os
import pkgutil
import re
import subprocess
import sys
from pathlib import Path

from make_venv import make_venv


def main():
    root = Path(__file__).parent.parent
    assert str(root) in sys.path
    if os.getenv('DRY_RUN'):
        _logger.info("Script is running in dry run mode, stop execution")
        return 0
    python = make_venv(root / 'linter')
    directories = [m.name for m in pkgutil.iter_modules([str(root)])]
    path_args = {Path(p).absolute() for p in sys.argv[1:]}  # Workdir if empty.
    # Don't exclude test (demo) files if paths are explicitly provided.
    # The test file for linter, which intentionally violates code style,
    # must be normally excluded. But it's tested if asked directly.
    excluded = {*root.glob('linter/demo*.py')} - path_args
    result = subprocess.run([
        python, '-m', 'flake8',
        '--append-config', root / 'linter/flake8_local_plugin.cfg',
        '--import-order-style=pycharm',
        '--max-line-length=150',
        '--hang-closing',
        '--application-import-names=' + ','.join(directories),
        '--ignore', (  # --extend-ignore is nicer but doesn't clear the default
            'B019,'  # Intended: @lru_cache() is allowed
            'D100,'  # Docstring is not mandatory in public modules.
            'D101,'  # Docstring is not mandatory in public classes.
            'D102,'  # Docstring is not mandatory in public methods.
            'D103,'  # Docstring is not mandatory in public functions.
            'D104,'  # Docstring is not mandatory in public packages.
            'D105,'  # Docstring is not mandatory in public magic methods.
            'D106,'  # Docstring is not mandatory in public nested classes.
            'D107,'  # Docstring is not mandatory in __init__.
            'D401,'  # TODO: What to do with context managers?
            'E126,'  # PyCharm and pycodestyle don't agree on continuation indent.
            'E501,'  # Intended: Replaced with X009.
            'W503,'  # Intended: line break must be before operator
            ''),
        '--extend-immutable-calls', (
            'IPv4Address,'
            'getuser,'
            'range,'
            'timedelta,'
            ''),
        *path_args,
        '--exclude=.*,' + ','.join(str(p) for p in excluded),
        ])
    st = [Path(p) for p in sys.argv[1:]] if sys.argv[1:] else [root]
    name_re = re.compile(rb'^[-\w]+')
    while st:
        entry = st.pop()
        if entry.is_dir() and not entry.name.startswith('.'):
            st.extend(entry.iterdir())
        if not fnmatch.fnmatch(entry.name, 'requirements*.txt'):
            continue
        lines = entry.read_bytes().splitlines(keepends=True)
        for lineno, (prev, line) in enumerate(zip(lines, lines[1:]), start=2):
            if name_re.match(line)[0].lower() < name_re.match(prev)[0].lower():
                print(f'{entry}:{lineno}: X901 Not in alphabetical order')
        if not lines[-1].endswith(b'\n'):
            print(f'{entry}:{len(lines)}: X902 No newline at the end of file')
    return result.returncode


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(main())
