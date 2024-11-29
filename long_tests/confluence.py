# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from abc import ABCMeta
from abc import abstractmethod
from base64 import b64encode
from enum import Enum
from functools import lru_cache
from netrc import netrc
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

_HOST = 'networkoptix.atlassian.net'


class Color(Enum):
    GREEN = '#abf5d1'
    RED = '#ffbdad'
    YELLOW = '#fff0b3'


class Alignment(Enum):
    LEFT = ''
    RIGHT = 'end'
    CENTER = 'center'


def get_confluence_page(page_id: str) -> '_Page':
    # See: https://developer.atlassian.com/cloud/confluence/rest/v2/
    request = Request(
        f'https://{_HOST}/wiki/api/v2/pages/{page_id}?body-format=atlas_doc_format',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': _make_auth_header(_HOST),
            },
        method='GET',
        )
    try:
        with urlopen(request, timeout=10) as response:
            return _Page(f'https://{_HOST}', json.loads(response.read()))
    except HTTPError as exc:
        with exc.fp:
            raise ConfluenceError(f'HTTP {exc.code}, error message: {exc.fp.read().decode("utf-8")}')


def write_confluence_page(page: '_Page', content: Mapping[str, Any]):
    # See: https://developer.atlassian.com/cloud/confluence/rest/v2/
    payload = json.dumps({
        'id': page['id'],
        'status': 'current',
        'title': page['title'],
        'body': {
            'representation': 'atlas_doc_format',
            'value': json.dumps(content),
            },
        'version': {
            'number': page['version']['number'] + 1,
            'message': 'Automatic update',
            },
        })
    request = Request(
        f'https://{_HOST}/wiki/api/v2/pages/{page["id"]}',
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': _make_auth_header(_HOST),
            'User-Agent': 'Mozilla/5.0',
            },
        data=payload.encode('utf-8'),
        method='PUT',
        )
    try:
        with urlopen(request) as response:
            json.loads(response.read())
    except HTTPError as exc:
        with exc.fp:
            raise ConfluenceError(f'HTTP code: {exc.code}, error message: {exc.fp.read()}')


@lru_cache()
def _make_auth_header(host: str) -> str:
    netrc_db = netrc(Path('~/.config/.secrets/confluence.netrc').expanduser())
    [username, _, password] = netrc_db.authenticators(host)
    token = b64encode(f'{username}:{password}'.encode('ascii')).decode('ascii')
    auth_header = f'Basic {token}'
    return auth_header


class Document:

    def __init__(self):
        self._data: List[Mapping[str, Any]] = []

    def get_data(self) -> Mapping[str, Any]:
        return {
            'type': 'doc',
            'version': 1,
            'content': self._data,
            }

    def add_content(self, content: '_Content'):
        self._data.append(content.get_data())


class _Content(metaclass=ABCMeta):

    @abstractmethod
    def get_data(self) -> Mapping[str, Any]:
        pass


class Table(_Content):

    def __init__(self, width: Optional[int] = None):
        self._data: List[Mapping[str, Any]] = []
        self._width = width

    def get_data(self) -> Mapping[str, Any]:
        attrs = {'width': self._width} if self._width is not None else {}
        return {
            'attrs': attrs,
            'type': 'table',
            'content': self._data,
            }

    def add_row(self, row: 'TableRow'):
        self._data.append(row.get_data())


class TableRow:

    def __init__(self):
        self._data: List[Mapping[str, Any]] = []

    def get_data(self) -> Mapping[str, Any]:
        return {
            'type': 'tableRow',
            'content': self._data,
            }

    def add_cells(
            self,
            values: Iterable[Any],
            align: Alignment = Alignment.LEFT,
            background: Optional[str] = None,
            link: Optional[str] = None,
            ):
        for v in values:
            marks = []
            if align != Alignment.LEFT:
                marks = [{
                    'type': 'alignment',
                    'attrs': {'align': align.value},
                    }]
            attrs = {
                'colspan': 1,
                'rowspan': 1,
                }
            if background is not None:
                attrs['background'] = background
            self._add_cell(v, 'tableCell', attrs, marks, link)

    def add_header_cells(
            self,
            values: Iterable[Any],
            width: int = 150,
            align: Alignment = Alignment.CENTER,
            colspan: int = 1,
            ):
        for v in values:
            marks = []
            if align != Alignment.LEFT:
                marks = [{
                    'type': 'alignment',
                    'attrs': {'align': align.value},
                    }]
            attrs = {
                'colspan': colspan,
                'rowspan': 1,
                'colwidth': [width] * colspan,
                }
            self._add_cell(v, 'tableHeader', attrs, marks)

    def _add_cell(
            self,
            value: Any,
            _type: str,
            attrs: Mapping[str, Any],
            marks: Sequence[Mapping[str, Any]],
            link: Optional[str] = None,
            ):
        inner_marks = []
        if link is not None:
            inner_marks.append({
                'type': 'link',
                'attrs': {'href': link},
                })
        cell = {
            'type': _type,
            'attrs': attrs,
            'content': [{
                'content': [{
                    'text': str(value),
                    'type': 'text',
                    }],
                'type': 'paragraph',
                }],
            }
        if marks:
            cell['content'][0]['marks'] = marks
        if inner_marks:
            cell['content'][0]['content'][0]['marks'] = inner_marks
        self._data.append(cell)


class TextBlock(_Content):

    def __init__(self, text: str):
        self._data = {
            'content': [{
                'type': 'text',
                'text': text,
                }],
            'type': 'paragraph',
            }

    def get_data(self) -> Mapping[str, Any]:
        return self._data


class _Page:

    def __init__(self, base_url: str, raw: Mapping[str, Any]):
        self._base_url = base_url
        self._raw = raw

    def __getitem__(self, item: str) -> Any:
        return self._raw[item]

    def get_link(self) -> str:
        return self._base_url + '/wiki' + self._raw['_links']['webui']


class ConfluenceError(Exception):
    pass
