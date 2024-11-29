# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import calendar
import json
from collections import Counter
from collections import defaultdict
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Collection
from typing import Generator
from typing import List
from typing import Mapping
from typing import NamedTuple

from flask import render_template
from flask import request

from infrastructure.ft_view import _db
from infrastructure.ft_view._enrichment import period_keys
from infrastructure.ft_view.web_ui._date_filter import DateFilter
from infrastructure.ft_view.web_ui._histogram import Histogram
from infrastructure.ft_view.web_ui._urls import parse_query


def list_runs_view():
    query_day_filter, order, query = parse_query(request.args)
    error = query.pop('error', '')
    limit = 1000
    raw = _db.select(
        'SELECT run_cmdline, run_json, run_ticket, run_message FROM run '
        'WHERE run_index @@ pg_temp.run_to_tsquery(%(query)s, %(error)s) '
        'LIMIT %(limit)s '
        ';', {
            'query': json.dumps(query),
            'error': error,
            'limit': limit,
            })
    _sort_runs(raw, order)
    warning = _warn_about_size(raw, limit)
    if len(raw) == 1:
        [row] = _db.select(
            'SELECT run_cmdline, run_json, run_ticket, run_message, run_artifacts FROM run '
            'WHERE run_index @@ pg_temp.run_to_tsquery(%(query)s, %(error)s) '
            'LIMIT 1 '
            ';', {
                'query': json.dumps(query),
                'error': error,
                })
        day_filter = DateFilter(row['run_json'].get('day'))
        row['run_artifacts'].sort(key=lambda url: (not url.endswith('.mp4'), url))
        raw = [row]
    else:
        day_filter = query_day_filter
    tickets = sorted({r['run_ticket'] for r in raw if r['run_ticket']})
    query_for_statistics = _with_period_instead_of_day(query)
    query_for_statistics = _with_default_period(query_for_statistics, day_filter.current_period())
    # In case of huge amount of failures
    failures_statistics = _query_failure_statistics(day_filter.today(), query_for_statistics, error, 10000)
    return render_template(
        'run_list.html',
        date_filter=day_filter,
        runs=raw,
        tickets=tickets,
        duration_statistics=Histogram(5, 600, [
            (r['run_json'].get('stage_status', 'unknown'), r['run_json'].get('report.duration_sec'))
            for r in raw
            if r['run_json'].get('report.duration_sec') is not None
            ]),
        failures_statistics=failures_statistics,
        warning=warning,
        )


def _warn_about_size(raw: Collection[str], limit: int):
    if len(raw) >= limit:
        return 'Too many results. Showing random. Add more filters.'
    elif not raw:
        return 'No results. Remove some filters.'
    else:
        return None


def _sort_runs(runs: List[str], order: str) -> None:
    if order == 'duration':
        runs.sort(
            reverse=True,
            key=lambda r: r['run_json'].get('report.duration_sec') if r['run_json'].get('report.duration_sec') is not None else -1,
            )
    elif order == 'name':
        runs.sort(key=lambda r: r['run_json'].get('args', ''))
    else:
        runs.sort(key=lambda r: r['run_json']['proc.started_at'], reverse=True)


def run_stats():
    date_filter, order, query = parse_query({'proc.username': 'ft', **request.args})
    query = _with_default_period(query, date_filter.current_period())
    failures_statistics = _query_failure_statistics(date_filter.today(), query, None, 10000000)
    total = failures_statistics.get_total_by_date(date_filter.focus_day().isoformat())
    failures = failures_statistics.get_failures_by_date(date_filter.focus_day().isoformat())
    if order == 'name':
        ids = sorted(total.keys())
    else:
        ids = sorted(
            total.keys(),
            key=lambda k: (failures[k], total[k], k),
            reverse=True,
            )
    return render_template(
        'run_stats.html',
        order=ids,
        date_filter=date_filter,
        failures_statistics=failures_statistics,
        )


def _with_default_period(query, period) -> Mapping[str, str]:
    if any(k.startswith('period.') for k in query):
        return query
    query = {**query, period: ''}
    assert any(k.startswith('period.') for k in query)
    return query


def _with_period_instead_of_day(query) -> Mapping[str, str]:
    if 'day' not in query:
        return query
    query = {**query}
    day = date.fromisoformat(query.pop('day'))
    for k in [*query.keys()]:
        if k.startswith('period.'):
            del query[k]
    query[min(period_keys(day))] = ''
    assert 'day' not in query
    return query


def _query_failure_statistics(today, run_data_filter, error_search_query, limit):
    raw_statistics = _db.select(
        'SELECT '
        'run_json->>$$day$$ AS day, '
        'run_json->>$$args$$ AS args, '
        'count(*) FILTER ( WHERE run_json->>$$report.status$$ = $$failed$$ ) as failed, '
        'count(*) as total '
        'FROM ('
        'SELECT * '
        'FROM run '
        'WHERE run_index @@ pg_temp.run_to_tsquery(%(query)s, %(error)s) '
        'LIMIT %(limit)s '
        ') AS limited '
        'GROUP BY run_json->>$$args$$, run_json->>$$day$$ '
        ';', {
            'query': json.dumps(run_data_filter),
            'error': error_search_query,
            'limit': limit,
            })
    failures_statistics = FailureStatistics(today)
    for run in raw_statistics:
        day = date.fromisoformat(run['day'])
        failures_statistics.add(run['args'], run['total'], run['failed'], day)
    return failures_statistics


class FailureStatistics:

    def __init__(self, today: date):
        self._today = today
        self._period = timedelta(days=28)
        self._latest_day: date = date.min
        self._earliest_day: date = date.max
        self._total = defaultdict(Counter)
        self._failures = defaultdict(Counter)

    def is_empty(self) -> bool:
        return not self._failures

    def add(self, test_id: str, total: int, fails_amount: int, date: datetime.date):
        self._earliest_day = min(self._earliest_day, date)
        self._latest_day = max(self._latest_day, date)
        date = date.isoformat()
        self._total[date][test_id] += total
        self._failures[date][test_id] += fails_amount

    def get_total_by_date(self, date: str) -> Counter:
        return self._total[date]

    def get_failures_by_date(self, date: str) -> Counter:
        return self._failures[date]

    def get_failures_total(self) -> int:
        return sum(f.fails for f in self.iter_over_failures())

    def get_failures_for_last_days(self, days: int) -> int:
        failures = list(self.iter_over_failures())
        return sum(f.fails for f in failures[-days:])

    def iter_over_failures(self) -> Generator['_Failures', None, None]:
        # Show exact number of days. Half-open interval, until not included.
        # If few days, pad with empty recent days. If many days, show latest.
        # Achieve a consistent look, few or many failures on a page.
        until = self._today + timedelta(days=1)
        until = min(until, self._earliest_day + self._period)
        until = max(until, self._latest_day + timedelta(days=1))
        since = until - self._period
        current_date = since
        while current_date < until:
            failures = self._failures[current_date.isoformat()]
            yield _Failures(current_date, failures.total())
            current_date += timedelta(days=1)

    def __len__(self):
        return (self._latest_day - self._earliest_day).days + 1


class _Failures(NamedTuple):
    date: date
    fails: int = 0

    def month_abbr(self) -> str:
        return calendar.month_abbr[self.date.month]
