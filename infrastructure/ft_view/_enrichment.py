# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import re
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
from http.client import HTTPException
from pathlib import Path
from typing import Any
from typing import Collection
from typing import Dict
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request
from urllib.request import urlopen

# Keep nightly runs from the same nights together in single day.
# Respect those who work through midnight.
# Consider 'midnight' to be set at 6 AM MSK.
# The below is the timezone where these days match wallclock days.
day_match_tz = timezone(timedelta(hours=-3))


def enrich(data):
    _enrich_with_build_info(data, 'opt.--installers-url')
    _enrich_with_git_info(data, 'env.COMMIT', 'ft/ft')
    _enrich_with_git_info(data, 'build_info.opt.--installers-url.changeSet', 'dev/nx')
    _enrich_with_day(data, 'created_at')  # Batches
    _enrich_with_day(data, 'proc.started_at')  # Runs
    _enrich_with_period(data, 'day', 5)
    _enrich_with_url_prefixes(data, 'opt.--installers-url')


def enrich_with_ticket(data: Dict[str, str], message: str):
    """Find Jira ticket URL in run message to display it in Web UI.

    >>> data = {}
    >>> message = "See: https://networkoptix.atlassian.net/browse/CLOUD-14463"
    >>> enrich_with_ticket(data, message)
    >>> data
    {'report.ticket': 'https://networkoptix.atlassian.net/browse/CLOUD-14463'}
    """
    if message is None:
        return
    pattern = re.compile(r'https://networkoptix.atlassian.net/browse/\w+-\d+')
    match = pattern.search(message)
    if match is None:
        return
    data['report.ticket'] = match.group(0)


def _enrich_with_day(data: Dict[str, Any], key: str):
    """Add key with the "official" day of the event. Same for all timezones.

    New key is not derived from source key: there's only one creation time.
    """
    if key not in data:
        return
    # Fix truncated ISO datetime.
    data[key] = re.sub(r'\.\d(?=\+)', r'\g<0>00000', data[key])
    data[key] = re.sub(r'\.\d\d(?=\+)', r'\g<0>0000', data[key])
    data[key] = re.sub(r'\.\d\d\d\d(?=\+)', r'\g<0>00', data[key])
    data[key] = re.sub(r'\.\d\d\d\d\d(?=\+)', r'\g<0>0', data[key])
    created_at = datetime.fromisoformat(data[key])
    day = created_at.astimezone(day_match_tz).date()
    data['day'] = day.isoformat()


def _enrich_with_period(data: Dict[str, Any], key: str, weeks: int):
    """Add periods containing event day. Respect ISO 8601.

    Use ISO 8601 format for period.
    Monday starts the week according to ISO 8601.
    New key is not derived from source key: there's only one creation day.
    """
    if key not in data:
        return
    day = date.fromisoformat(data[key])
    for period_key in period_keys(day):
        data[period_key] = ''


def period_keys(day: date) -> Collection[str]:
    periods = []
    weeks = 5
    for i in range(weeks):
        # Year to which the week belongs. Differs from actual around New Year.
        year, week, _weekday = (day - timedelta(days=7 * i)).isocalendar()
        periods.append(f'period.{year}-W{week:02d}/P{weeks}W')
    return periods


def _enrich_with_url_prefixes(data: Dict[str, Any], key: str):
    if key not in data:
        return
    for m in re.finditer('/+', data[key]):
        data['url.' + key + '.' + data[key][:m.end()]] = ''


def _enrich_with_build_info(data: Dict[str, Any], key: str):
    if key not in data:
        return
    url = data[key].removesuffix('/') + '/' + 'build_info.txt'
    try:
        raw = _get_text(url)
    except (URLError, HTTPException) as e:
        data['build_info.' + key + '.error'] = _extract_error(e)
        return
    for line in raw.splitlines():
        try:
            line = line.decode()
        except UnicodeDecodeError:
            continue
        [k, _, v] = line.partition('=')
        data['build_info.' + key + '.' + k] = v


@lru_cache(2000)
def _get_text(url: str) -> bytes:
    try:
        with urlopen(url) as response:
            return response.read()
    except HTTPError as e:
        if e.code == 404:
            return b''
        raise


def _enrich_with_git_info(data: Dict[str, Any], key: str, project: str):
    if key not in data:
        return
    ref = data[key]
    try:
        commit = _gitlab_get('/projects/:id/repository/commits/:sha', project, ref)
    except (URLError, HTTPException) as e:
        data['git.' + key + '.error'] = _extract_error(e)
        return
    if not commit:
        return
    data['git.' + key + '.sha'] = commit['id']
    data['git.' + key + '.url'] = commit['web_url']
    data['git.' + key + '.author_email'] = commit['author_email']
    data['git.' + key + '.author_name'] = commit['author_name']
    data['git.' + key + '.author_date'] = commit['authored_date']
    data['git.' + key + '.committer_email'] = commit['committer_email']
    data['git.' + key + '.committer_name'] = commit['committer_name']
    data['git.' + key + '.committer_date'] = commit['committed_date']
    if commit.get('last_pipeline'):
        data['pipeline.' + key + '.id'] = commit['last_pipeline']['id']
        data['pipeline.' + key + '.url'] = commit['last_pipeline']['web_url']
    try:
        mr = _gitlab_get('/projects/:id/repository/commits/:sha/merge_requests', project, ref)
    except (URLError, HTTPException) as e:
        data['mr.' + key + '.error'] = _extract_error(e)
        return
    if not mr:
        return
    data['mr.' + key + '.id'] = mr[0]['iid']
    data['mr.' + key + '.url'] = mr[0]['web_url']
    m = re.match(r'[A-Z]+-\d+(?=:)', mr[0]['title'])
    if m:
        data['mr.' + key + '.ticket'] = m[0]


@lru_cache(2000)
def _gitlab_get(path, project, *values):
    for arg in [project, *values]:
        path = re.sub(r'(?<=/):\w+(?=/|$)', quote_plus(arg), path, 1)
    url = 'https://gitlab.nxvms.dev/api/v4' + path
    request = Request(url, headers={'PRIVATE-TOKEN': _tokens[project]})
    try:
        with urlopen(request, timeout=10) as response:
            data = response.read()
    except HTTPError as e:
        if e.code == 404:  # Not transient (e.g. removed VMS build). Cache it.
            return None
        raise
    # Do not suppress exceptions here to avoid caching erroneous states.
    return json.loads(data)


def _extract_error(e: URLError | HTTPException) -> str:
    """Extract and save errors to find them and try again later manually."""
    if isinstance(e, HTTPException):  # Example: BadStatusLine
        return e.__class__.__name__
    elif isinstance(e, HTTPError):  # Example: HTTP 403
        return str(e.code)
    elif e.__context__ is not None:  # Example: SSLError, PermissionError
        return e.__context__.__class__.__name__
    else:  # Fallback
        return e.reason


_tokens = {
    'dev/nx': Path('~/.config/.secrets/gitlab_project_token_dev_nx.txt').expanduser().read_text(),
    'ft/ft': Path('~/.config/.secrets/gitlab_project_token_ft_ft.txt').expanduser().read_text(),
    }
