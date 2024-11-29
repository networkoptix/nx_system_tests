# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import Sequence

from _internal.service_registry import elasticsearch
from _internal.service_registry import gitlab_dev_nx
from long_tests.confluence import Alignment
from long_tests.confluence import Document
from long_tests.confluence import Table
from long_tests.confluence import TableRow
from long_tests.confluence import TextBlock
from long_tests.confluence import get_confluence_page
from long_tests.confluence import write_confluence_page


def load_measurements(
        query: str,
        key_fields: Collection[str] = (),
        ) -> Sequence[Mapping[str, Any]]:
    result = elasticsearch.search('ft-measure-*', query)
    documents = []
    for data in result['hits']['hits']:
        doc = data['_source']
        doc['started_at'] = datetime.fromisoformat(doc['started_at'])
        doc['finished_at'] = datetime.fromisoformat(doc['finished_at'])
        doc['installers_url'] = doc['installers_url'].rstrip('/')
        documents.append(doc)
    documents.sort(key=lambda x: x['started_at'], reverse=True)
    # Select the latest documents for every branch
    result = []
    last_docs = set()
    for doc in documents:
        version_parts = doc['version'].split('.')
        version_short = '.'.join(version_parts[:3])
        key_values = [doc[k] for k in key_fields]
        version_id = (doc['type'], doc['installer_type'], version_short, *key_values)
        if version_id not in last_docs:
            last_docs.add(version_id)
            result.append(doc)
    return result


def parse_args(args: Sequence[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--all-types',
        action='store_true',
        default=False,
        help="Build a report with all distrib types",
        )
    return parser.parse_args(args)


class BuildInfo(NamedTuple):
    version: str
    installer_type: str
    change_set: str
    installers_url: str
    sorting_key: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]):
        if 'change_set' not in data:
            raise RuntimeError('No change set found')
        return cls(
            version=data['version'],
            installer_type=data['installer_type'],
            change_set=data['change_set'],
            installers_url=data['installers_url'],
            sorting_key=_construct_sorting_key(data['version'], data['change_set']),
            )


class ComparisonReport(metaclass=ABCMeta):

    def __init__(self, measurements_raw: Collection[Mapping[str, Any]]):
        self._measurements_raw = measurements_raw

    @abstractmethod
    def create(self) -> str:
        pass


class ComparisonReportConfluence(ComparisonReport, metaclass=ABCMeta):

    def __init__(self, page_id: str, measurements_raw: Collection[Mapping[str, Any]]):
        super().__init__(measurements_raw)
        self._page_id = page_id

    @abstractmethod
    def _build_document(self) -> Document:
        pass

    def create(self) -> str:
        doc = self._build_document()
        page = get_confluence_page(self._page_id)
        _logger.info("%s: saving report to %s", self.__class__.__name__, page.get_link())
        write_confluence_page(page, doc.get_data())
        return page.get_link()

    @staticmethod
    def _get_stand_info_block(os_name: str, cpu: int, ram: int) -> TextBlock:
        return TextBlock(
            f"\tOS: {os_name}\n"
            f"\tCPU: {cpu}\n"
            f"\tRAM: {ram}\n")

    @staticmethod
    def _get_builds_table(builds: Collection[BuildInfo]) -> Table:
        table = Table(1200)
        row = TableRow()
        row.add_header_cells(['Version', 'Type', 'Change set'])
        row.add_header_cells(['Distributive'], width=700)
        table.add_row(row)
        for line in sorted(builds, key=lambda build: build.version):
            row = TableRow()
            row.add_header_cells([line.version], align=Alignment.CENTER)
            row.add_cells([line.installer_type, line.change_set], align=Alignment.CENTER)
            row.add_cells([line.installers_url], link=line.installers_url)
            table.add_row(row)
        return table


def _construct_sorting_key(version: str, change_set: str) -> str:
    # The committer date usually changes after a rebase, and it may be assumed that commits are
    # placed in the order of the committer date. There are a few exceptions, but for that task,
    # it doesn't matter.
    commit = gitlab_dev_nx.get_commit(change_set)
    commit_last_timestamp = commit.committed_date().astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
    [major, minor, patch, _] = version.strip().split('.')
    sorting_key = major.ljust(2, '0') + minor.ljust(2, '0') + patch.ljust(2, '0') + commit_last_timestamp
    return sorting_key


class FailLoadMeasurements(Exception):
    pass


_logger = logging.getLogger(__name__)
