# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import inspect
import logging
import os
import os.path
import re
import shlex
import sys
from abc import ABCMeta
from abc import abstractmethod
from argparse import ArgumentParser
from contextlib import ExitStack
from traceback import format_exception
from typing import Collection
from typing import List
from typing import Mapping
from typing import Sequence
from typing import Tuple
from typing import Type

from _internal.service_registry import elasticsearch
from _internal.service_registry import ft_view_reporter
from cloud_api.cloud import ChannelPartnersNotSupported
from config import global_config
from directories import clean_up_artifacts
from directories import get_run_dir
from directories import run_metadata
from directories import standardize_module_name
from directories import standardize_script_name
from distrib import APINotSupported
from distrib import BranchNotSupported
from distrib import OSNotSupported
from distrib import SpecificFeatureNotSupported
from distrib import UpdatesNotSupported
from infrastructure.elasticsearch_logging import ElasticsearchHandler
from infrastructure.ft_view.run_updates_reporter import StageReporter
from runner.reporting.pretty_traceback import dump_traceback


def run_ft_test(argv: Sequence[str], ft_tests: 'Collection[FTTest]'):
    by_name = {t.__class__.__name__: t for t in ft_tests}
    parser = ArgumentParser(prog=standardize_script_name(argv[0]))
    if len(by_name) == 1:
        [[name, ft_test]] = by_name.items()
        parser.add_argument(
            'test',
            choices=[name],
            nargs='?',
            default=name,
            )
        ft_test.add_argparse_parameters(parser)
    else:
        subparsers = parser.add_subparsers(dest='test', required=True)
        for t in by_name.values():
            subparser = subparsers.add_parser(t.__class__.__name__)
            t.add_argparse_parameters(subparser)
    parsed = parser.parse_args(argv[1:])
    ft_test = by_name[parsed.test]
    _logger.info("Test id: %s", ft_test)
    if os.getenv('DRY_RUN'):
        print(f"Dry run: Would run test {ft_test!r} with args {parsed}")
        return 0
    else:
        return ft_test.run_with_reporting(parsed)


class FTTest(metaclass=ABCMeta):

    def __init__(self):
        self._argparse_parameters: List[Tuple[str, Type[argparse.Action]]] = []

    def __repr__(self):
        return f'<FTTest {shlex.join(self._positional_args())}>'

    def add_argparse_parameters(self, parser):
        for name, action in self.list_argparse_parameters():
            parser.add_argument(name, action=action)

    def list_argparse_parameters(self) -> Collection[Tuple[str, Type[argparse.Action]]]:
        return self._argparse_parameters

    def has_tag(self, tag: str):
        return tag in self._tags()

    def _tags(self) -> Collection[str]:
        return [*self._dir_tags(), *self._custom_tags()]

    def _custom_tags(self) -> Collection[str]:
        tags = []
        docstring = inspect.getdoc(self)
        if docstring is None:
            return []
        p = 'https://networkoptix.testrail.net/index.php?/cases/view/'
        for line in docstring.splitlines():
            if line.startswith('Selection-Tag:'):
                tags.append(line.removeprefix('Selection-Tag:').strip())
            if line.startswith('TestRail:'):
                value = line.removeprefix('TestRail:').strip()
                m = re.fullmatch(re.escape(p) + r'(\d+)', value)
                tags.append(f'testrail-{m[1]}')
        return tags

    def _dir_tags(self) -> Collection[str]:
        file_id = self._file_id()
        return [
            'dir:' + file_id[:i + 1]
            for i in range(len(file_id))
            if file_id[i] == '/'
            ]

    def main(self):
        parser = argparse.ArgumentParser(prog=standardize_script_name(sys.argv[0]))
        self.add_argparse_parameters(parser)
        args = parser.parse_args()
        if os.getenv('DRY_RUN'):
            print(f"Dry run: Would run test {self} with args {args}")
            return 0
        else:
            return self.run_with_reporting(args)

    def run_with_reporting(self, args: argparse.Namespace):
        logging.getLogger().setLevel(logging.DEBUG)  # Default is warning
        standard_formatter = logging.Formatter((
            '%(asctime)s '
            '%(threadName)10s '
            '%(name)s '
            '%(levelname)s '
            '%(message)s'))
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(standard_formatter)
        stream_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(stream_handler)
        clean_up_artifacts()
        run_dir = get_run_dir()
        # On Windows, encoding is one-byte by default. Hence explicit UTF-8.
        file_handler = logging.FileHandler(run_dir / 'debug.log', encoding='utf8')
        file_handler.setFormatter(standard_formatter)
        logging.getLogger().addHandler(file_handler)
        os.environ['SSLKEYLOGFILE'] = os.fspath(run_dir / 'ssl_keylog.txt')
        run_properties = {
            **run_metadata(),
            'run_cmdline': self.serialize(args, os.getenv('RUN_MACHINERY'))['cmdline'],
            }
        if global_config.get('elasticsearch_logging_enabled') == 'true':
            elasticsearch_handler = ElasticsearchHandler(elasticsearch, 'ft-logs-{YYYY}-{MM}', run_properties)
            elasticsearch_handler.setLevel(logging.INFO)
            logging.getLogger().addHandler(elasticsearch_handler)
        with StageReporter(ft_view_reporter, run_dir, run_properties) as reporter:
            # Send the run URL to stdout, so it can be propagated further and logged as needed.
            print(f"Run URL: {reporter.get_run_url()}", flush=True)
            try:
                with ExitStack() as exit_stack:
                    _logger.info("Test: Start")
                    self._run(args, exit_stack)
            except (
                    APINotSupported,
                    BranchNotSupported,
                    ChannelPartnersNotSupported,
                    OSNotSupported,
                    SpecificFeatureNotSupported,
                    UpdatesNotSupported,
                    ) as e:
                _logger.exception("Test: Skipped")
                run_url = reporter.set_skipped(str(e))
                _logger.info("Artifact dir: %s", run_dir)
                _logger.info("FT View run URL: %s", run_url)
                return int(os.getenv('FAILURE_EXIT_CODE', '0'))
            except Exception as e:
                _logger.exception("Test: Exception")
                dump_traceback(e, run_dir)
                run_url = reporter.set_failed(''.join(format_exception(e)).rstrip())
                _logger.info("Artifact dir: %s", run_dir)
                _logger.info("FT View run URL: %s", run_url)
                return int(os.getenv('FAILURE_EXIT_CODE', '0'))
            else:
                _logger.info("Test: Normal return")
                run_url = reporter.set_passed()
                _logger.info("Artifact dir: %s", run_dir)
                _logger.info("FT View run URL: %s", run_url)
                return 0

    def _positional_args(self) -> Sequence[str]:
        return ['-m', standardize_module_name(self._file_id())]

    def _keyword_args(self, args) -> Mapping[str, str]:
        return {
            key: getattr(args, action.dest)
            for key, action in self.list_argparse_parameters()
            }

    def _file_id(self):
        return standardize_script_name(inspect.getfile(self.__class__))

    @abstractmethod
    def _run(self, args: argparse.Namespace, exit_stack: ExitStack):
        pass

    def serialize(self, args: argparse.Namespace, machinery: str):
        git_current_sha = run_metadata()['run_ft_revision']
        return {
            'cmdline': {
                # Why Mapping[str, str]?
                # - Easy to represent: JSON, urlencoded, .ini etc.
                # - East to define a subset and use it as a search query.
                # - Easy to index and search in schemaless fields (JSONB in
                #   Postgres) or no-SQL DBs (Elasticsearch).
                # - Env vars and optional args are equal regardless of order.
                # - The shell style 'FOO=bar prog --opt=val' is concise but
                #   hard to parse correctly: any quote in a var name spoils it.
                # - The delimiter '.' is transparent in urlencode().
                'env.COMMIT': git_current_sha,
                'env.MACHINERY': machinery,
                'exe': shlex.join(['python', '-m', 'make_venv']),
                'args': shlex.join(self._positional_args()),
                **{
                    'opt.' + k: v
                    for k, v in self._keyword_args(args).items()
                    },
                },
            'marks': self._tags(),
            'stage_url': (
                'https://gitlab.nxvms.dev/ft/ft/-/blob'
                f'/{git_current_sha}/{self._file_id()}'
                f'#L{self._run.__code__.co_firstlineno + 1}'),
            }


_logger = logging.getLogger(__name__)
