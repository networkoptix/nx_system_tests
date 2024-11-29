# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import importlib
import inspect
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath
from typing import Collection
from typing import Mapping
from typing import Type
from urllib.parse import urljoin
from urllib.request import urlopen

from config import global_config
from runner.ft_test import FTTest

_logger = logging.getLogger(__name__)


def run_batch_main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--machinery', default=global_config['ft_machinery_url'])
    parser.add_argument('--priority', default='normal', choices=['low', 'normal', 'high'])
    common_args, _extras = parser.parse_known_args(args)
    collection = _Collection()
    if common_args.tag.startswith('dir:'):
        lookup_dir = common_args.tag.removeprefix('dir:')
        collection.collect(lookup_dir, 'test_*.py', common_args.tag)
    else:
        collection.collect('tests', 'test_*.py', common_args.tag)
    _logger.info("Statistics: %s", collection)
    for key, action in collection.argparse_params().items():
        parser.add_argument(key, action=action)
    parsed_args = parser.parse_args(args)
    batch_dict = {
        'cmdline': {
            'env.COMMIT': os.getenv('FT_COMMIT') or subprocess.getoutput('git rev-parse HEAD'),
            'exe': shlex.join(['python', '-m', 'make_venv']),
            'args': shlex.join(['-m', 'runner.run_batch']),
            'opt.--machinery': parsed_args.machinery,
            'opt.--tag': parsed_args.tag,
            **{
                'opt.' + key: getattr(parsed_args, action.dest)
                for key, action in collection.argparse_params().items()
                },
            },
        }
    start_data = {
        'args': batch_dict,
        'tests': [
            t.serialize(parsed_args, parsed_args.machinery)
            for t in collection.tests()
            ],
        'schedule_priority': parsed_args.priority,
        }
    print(f"Run a batch of {len(collection.tests())} tests: {batch_dict}")
    cmd = ['git', 'diff', os.getenv('FT_COMMIT') or 'HEAD', '--quiet']
    run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if run.stdout:
        print(run.stdout.decode(errors='backslashreplace'))
        return 1
    elif run.returncode != 0:
        print(
            "Uncommitted changes: Will not start batch; "
            "otherwise, results would be misleading: "
            "workers would check out committed code, without local changes")
        return 10
    if os.getenv('DRY_RUN'):
        print("Dry run: Would start batch and poll for completion")
        return 0
    start_url = _root_url + '/batches/start'
    _logger.info("POST %s", start_url)
    response = urlopen(start_url, json.dumps(start_data).encode(), timeout=120)
    batch_url = urljoin(start_url, response.headers['Location'])
    print(batch_url, flush=True)
    batch_timeout_at = time.monotonic() + 3600
    summary_interval = 60
    last_summary_update_at = float('-inf')
    while True:
        _logger.info("GET: %s", batch_url)
        response = urlopen(batch_url, timeout=120)
        content = response.read()
        stats = json.loads(content)
        now = time.monotonic()
        summary = ' '.join(f'{k}={v}' for k, v in stats.items())
        if now - last_summary_update_at > summary_interval:
            print(summary, flush=True)
            last_summary_update_at = now
        if stats['failed_count'] > 0:
            print(summary, flush=True)
            return 10
        if stats['pending_count'] == 0:
            return 0
        if time.monotonic() > batch_timeout_at:
            print(summary, 'timeout', flush=True)
            return 9
        time.sleep(5)


class _Collection:

    def __init__(self):
        self._tests = []
        self._argparse_params = {}
        self._stats = Counter()

    def __repr__(self):
        return f'<_Collection {self._stats}>'

    def tests(self) -> Collection[FTTest]:
        return self._tests

    def argparse_params(self) -> Mapping[str, Type[argparse.Action]]:
        return self._argparse_params

    def collect(self, path: str, pattern: str, tag: str):
        _logger.info("Collect tests with tag %s", tag)
        for test_file in _repo_dir.joinpath(path).rglob(pattern):
            rel = test_file.relative_to(_repo_dir)
            module_name = '.'.join(rel.with_suffix('').parts)
            module = importlib.import_module(module_name)
            for member in module.__dict__.values():
                if inspect.getmodule(member) != module:
                    continue  # Imported, not defined in this module. Skip.
                if inspect.isabstract(member):
                    continue
                if not (isinstance(member, type) and issubclass(member, FTTest)):
                    continue  # Not a test, something else.
                test = member()
                if not test.has_tag(tag):
                    continue
                _logger.info('Collected test: %s', test)
                self._tests.append(test)
                for key, action in test.list_argparse_parameters():
                    if key not in self._argparse_params:
                        self._argparse_params[key] = action
                    elif self._argparse_params[key] is action:
                        pass
                    else:
                        raise ValueError(f"{key} defined twice")
                self._stats[str(PurePosixPath(path, '**', pattern))] += 1


_repo_dir = Path(__file__).parent.parent.resolve()
_root_url = global_config['ft_view_url'].rstrip('/')

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(run_batch_main(sys.argv[1:]))
