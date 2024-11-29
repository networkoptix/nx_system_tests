# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import doctest
import fnmatch
import importlib
import logging
import os
import re
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Collection


def main(args):
    p = _RecursiveDoctest(_repo_root, [
        'os_access/local_shell/local_windows_shell.py',
        'vm/virtual_box/run_as_user/_windows_run_as_user.py',
        'infrastructure/ft_view',
        'task_master_service',
        'real_camera_tests',
        'arms',
        'tests/gui',
        'self_tests/arms',
        'venv',
        'linter/demo*.py',
        'module_imports',
        'infrastructure',
        ])
    parser = ArgumentParser()
    parser.add_argument(
        'path',
        nargs='?',
        default=_repo_root,
        help='file or dir to test, default: %(default)s',
        type=lambda v: Path(v).absolute(),
        )
    parsed_args = parser.parse_args(args)
    if os.getenv('DRY_RUN'):
        _logger.info("Dry run: would run a doctests")
        return 0
    results = p.run(parsed_args.path)
    if results.failed > 0:
        return 10
    else:
        return 0


class _RecursiveDoctest:

    def __init__(self, root: Path, exclude: Collection[str]):
        self._root: Path = root
        exclude = [
            '.*',
            '*/.*',
            'setup.py',
            '*/setup.py',
            '__pycache__',
            '*/__pycache__',
            *exclude,
            ]
        patterns = [fnmatch.translate(e) for e in exclude]
        self._exclude_re = re.compile('|'.join(patterns))
        self._runner = doctest.DocTestRunner()
        self._finder = doctest.DocTestFinder()

    def run(self, path: Path):
        if path.is_dir():
            self._test_dir(path)
        else:
            self._test_file(path)
        return self._runner.summarize(verbose=True)

    def _test_dir(self, d):
        for entry in os.scandir(d):
            path = Path(entry.path)
            if self._is_excluded(path):
                _logger.debug("Exclude: %s", path)
            elif entry.is_dir():
                _logger.debug("Test dir: %s", path)
                self._test_dir(path)
            elif path.suffix == '.py':
                _logger.debug("Test file: %s", path)
                self._test_file(path)
            else:
                _logger.debug("Not Python: %s", path)

    def _test_file(self, path: Path):
        module = importlib.import_module(self._file_to_module(path))
        for test in self._finder.find(module):
            if test.examples:
                self._runner.run(test)

    def _file_to_module(self, path: Path):
        path = path.relative_to(self._root)
        return '.'.join(path.with_suffix('').parts)

    def _is_excluded(self, path: Path):
        normalized = path.relative_to(self._root).as_posix()
        return self._exclude_re.fullmatch(normalized) is not None


_repo_root = Path(__file__).parent.parent
assert str(_repo_root) in sys.path

_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    exit(main(sys.argv[1:]))
