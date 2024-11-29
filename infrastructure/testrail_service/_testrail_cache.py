# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from infrastructure.testrail_service._testrail_api import _GetApi

DEFAULT_CACHE_PATH = Path('~/.cache/testrail_cache.json').expanduser()


class CacheResponseDecorator(_GetApi):

    def __init__(self, api: _GetApi):
        self._api = api
        self._base_url = api.base_url()
        self._cache = {'base_url': self._base_url}

    def base_url(self):
        return self._base_url

    def get(self, uri: str):
        if uri not in self._cache:
            self._cache[uri] = self._api.get(uri)
        return deepcopy(self._cache[uri])

    def save(self, path: Path):
        path.write_text(json.dumps(self._cache, indent=4) + '\n')


class TestRailCache(_GetApi):
    """Make requests to cache as if it's real TestRail.

    Reporting test results to TestRail requires many API requests, which are
    very slow. (At least, because TestRail is used as a SaaS, not as a hosted
    service.) Downloading all the data required for reporting takes several
    minutes. That's why crawling data is performed as a separate step, which is
    invoked manually. Then, all the reports are generated using the crawled
    data, and only POST requests with actual reports are made to the real
    TestRail instance.
    """

    def __init__(self, cache_path: Path):
        self._cache_path = cache_path
        self._cache = {}
        self._read()

    def base_url(self):
        return self._base_url

    def get(self, path):
        return self._cache[path]

    def refresh(self) -> 'TestRailCache':
        if self._modification_timestamp != self._cache_path.stat().st_mtime:
            self._read()
        return self

    def get_age(self) -> str:
        loaded_date = datetime.fromtimestamp(self._modification_timestamp)
        now_date = datetime.fromtimestamp(time.time())
        delta = now_date - loaded_date
        minutes, _seconds = divmod(delta.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        parts = []
        for value, noun in ((delta.days, 'day'), (hours, 'hour'), (minutes, 'minute')):
            if value:
                plural = "s" if value != 1 else ""
                parts.append(f"{value} {noun}{plural}")
        if len(parts) > 1:
            return ", ".join(parts[:-1]) + " and " + parts[-1] + " ago"
        elif len(parts) == 1:
            return parts[0] + " ago"
        else:
            return "< 1 minute ago"

    def _read(self):
        self._cache = json.loads(self._cache_path.read_text())
        self._base_url = self._cache['base_url']
        self._modification_timestamp = self._cache_path.stat().st_mtime
