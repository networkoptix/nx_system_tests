# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
from fnmatch import fnmatch
from typing import Dict
from typing import Mapping
from urllib.parse import urlencode

from flask import current_app
from flask import redirect
from flask import request

from infrastructure.ft_view.web_ui._date_filter import DateFilter


def _redirect_back():
    """Define what to respond if action has no result data."""
    if request.referrer is None:
        return b'', 204
    return redirect(request.referrer, 302)


class URLParamSet:
    """Support index page URL (no params) and URL manipulation.

    Index page URL must be URL with some default filters.
    Because the URL is treated as a filter that used in SQL,
    empty URL formally means filtering nothing, showing everything.
    Resolve this with a special URL value.

    >>> s = URLParamSet.from_flask({}, {'de': 'fault'})
    >>> s.href()
    '.'
    >>> s.removed('de').href()
    '?everything='
    >>> s = URLParamSet.from_flask({'everything': ''}, {'de': 'fault'})
    >>> s.removed('missing').added('some', 'param').href()
    '?some=param'
    """

    def __init__(self, params: Mapping[str, str], default: Mapping[str, str]):
        self._default = default
        self._params = params

    @staticmethod
    def from_flask(params: Mapping[str, str], default: Mapping[str, str]):
        params = {**params}  # Flask's request.args is not a dict.
        clean_params = (
            default if not params else
            {} if params == {'everything': ''} else
            params)
        return URLParamSet(clean_params, default)

    def to_flask(self):
        return (
            {} if self._params == self._default else
            {'everything': ''} if not self._params else
            self._params)

    def href(self):
        params = self.to_flask()
        encoded = query_string(**params)
        if encoded:
            return encoded
        else:
            # Result of this function is the entire value of a 'href' attribute.
            # If it's empty, query string from the current URL is not removed.
            # A single question mark appears in the resulting URL.
            # A period removes GET params and dissolves in the resulting URL.
            return '.'

    def added(self, key: str, value: str) -> 'URLParamSet':
        return URLParamSet({**self._params, key: value}, self._default)

    def removed(self, glob: str) -> 'URLParamSet':
        new = {k: v for k, v in self._params.items() if not fnmatch(k, glob)}
        return URLParamSet(new, self._default)

    def params(self) -> Mapping[str, str]:
        return self._params


def query_string(**url_params):
    url_params = {k: v for k, v in url_params.items() if v is not None}
    if not url_params:
        return ''
    # Maintain fixed order of GET parameters.
    order = ['username', 'hostname', 'day']
    url_params_sorted = {}
    for param in order:
        if param in url_params:
            url_params_sorted[param] = url_params.pop(param)
    for param in sorted(url_params.keys()):
        url_params_sorted[param] = url_params.pop(param)
    return '?' + urlencode(url_params_sorted)


def parse_query(raw_query: Mapping[str, str]):
    query = _update_obsolete(raw_query)
    if query != {**raw_query}:  # It's usually request.args
        query_check = _update_obsolete(query)
        if query == query_check:
            current_app.logger.debug(
                "URL normalization performed, expect redirect: "
                "raw=%s -> normalized=%s",
                raw_query, query)
            raise ObsoleteURL(query_string(**query))
        else:
            current_app.logger.error(
                "URL normalization not idempotent, avoid infinite redirect: "
                "raw=%s -> normalized_once=%s -> normalized_twice=%s",
                raw_query, query, query_check)
    order = query.pop('order', None)
    date_filter = DateFilter(query.get('day'))
    query = URLParamSet.from_flask(query, {date_filter.current_period(): ''}).params()
    return date_filter, order, query


def _update_obsolete(raw_query: Mapping[str, str]) -> Dict[str, str]:
    query: Dict[str, str] = {}
    for k, v in raw_query.items():
        if k == 'started_at':
            if re.search(r'[-+]\d\d:\d\d$', v):
                query['proc.started_at'] = v
            else:
                query['proc.started_at'] = v + '+00:00'  # URL from Reporter
        elif k == 'args':
            if v.startswith(('tests/', 'suites/')):
                query['args'] = '-m ' + v.replace('.py', '').replace('::', ' ').replace('/', '.')
            else:
                query['args'] = v
        elif k == 'run_vms_url':
            if v.endswith('*'):
                prefix = v.removesuffix('*')
                query['url.opt.--installers-url.' + prefix] = ''
            else:
                query['opt.--installers-url'] = v
        elif k in _obsolete_synonyms:
            query[_obsolete_synonyms[k]] = v
        else:
            query[k] = v
    return query


_obsolete_synonyms = {
    'run_ft_revision': 'env.COMMIT',
    'tag': 'opt.--tag',
    'machinery': 'opt.--machinery',
    'vms': 'opt.--installers-url',
    'run_vms_revision': 'git.build_info.opt.--installers-url.changeSet.sha',
    'username': 'proc.username',
    'hostname': 'proc.hostname',
    'pid': 'proc.pid',
    }


class ObsoleteURL(Exception):

    def __init__(self, updated_url: str):
        self.updated_url: str = updated_url
