# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import fnmatch
import importlib
import logging
import os
import sys
import unittest
from pathlib import Path
from pathlib import PurePath


def main():
    found = _walk('test_*.py', exclude=['arms', 'arm_tests', 'venv'])
    suite = unittest.TestSuite()
    for python_file in found:
        module_name = _build_module_name(python_file)
        logging.debug("Import: %s", module_name)
        module = importlib.import_module(module_name)
        logging.debug("Load: %r", module)
        scope = unittest.defaultTestLoader.loadTestsFromModule(module)
        if scope.countTestCases() > 0:
            logging.debug("Will run: %r as %r", module, scope)
            suite.addTests(scope)
        else:
            logging.debug("Skip empty: %r", module)
    if os.getenv('DRY_RUN'):
        _logger.info("Dry run: would run a unittests")
        return 0
    logging.info("Run tests")
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        return 0
    else:
        return 10


def _walk(pattern: str, *, exclude):
    """Discover all tests recursively, but do not recurse in special dirs.

    >>> _walk('test_*.py', exclude=['arms', 'arm_tests', 'venv'])  # doctest: +ELLIPSIS
    [...Path...Path...Path...]
    """
    exclude = [_root / x for x in exclude] + ['__pycache__']
    stack = [_root]
    logging.info("Search %r for %r excluding %r", stack, pattern, exclude)
    result = []
    while stack:
        f = stack.pop()
        if f.name.startswith('.'):
            logging.debug("Skip starting with dot: %s", f)
        elif f.is_dir():
            if f in exclude:
                logging.debug("Skip excluded: %s", f)
            else:
                logging.debug("Recurse: %s", f)
                stack.extend(f.iterdir())
        elif f.is_file():
            if fnmatch.fnmatch(f.name, pattern):
                logging.debug("Collect: %s", f)
                result.append(f)
            else:
                logging.debug("Skip unknown file suffix: %s", f)
        else:
            logging.debug("Skip unknown file type: %s", f)
    return result


def _build_module_name(path: PurePath):
    """Build module name from path.

    >>> _build_module_name(_root / 'foo/bar.py')
    'foo.bar'
    """
    path = path.relative_to(_root)
    path = path.with_suffix('')
    return '.'.join(path.parts)


_logger = logging.getLogger(__name__)
_root = Path(__file__).parent.parent
assert str(_root) in sys.path

if __name__ == '__main__':
    exit(main())
