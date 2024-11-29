# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import json
import logging
import shlex
from datetime import datetime
from typing import List
from typing import Mapping

from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.exceptions import Forbidden

from infrastructure.ft_view import _db
from infrastructure.ft_view._db import WriteForbiddenError
from infrastructure.ft_view.web_ui._urls import _redirect_back
from infrastructure.ft_view.web_ui._urls import parse_query

_logger = logging.getLogger(__name__)
batches_blueprint = Blueprint(
    'batches',
    __name__,
    )


def _reraise_on_db_write_error(func):
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except WriteForbiddenError:
            raise Forbidden("No write access to DB")
    return decorated


@batches_blueprint.route('/')
@_reraise_on_db_write_error
def _list():
    date_filter, order, batch_filter = parse_query(request.args)
    result = _db.select(
        'SELECT batch.* '
        'FROM batch '
        'WHERE data @> %(filter)s::jsonb '
        'ORDER BY created_at DESC '
        'LIMIT 100 '
        ';', {
            'filter': json.dumps(batch_filter),
            })
    result = [
        batch | {
            'created_at': batch['created_at'].isoformat(timespec='microseconds'),
            'job_count': sum(
                value or 0
                for key, value in batch['data'].items()
                if key.startswith('count.')
                ),
            'cmdline_script': _cmdline_to_str(batch['cmdline']),
            }
        for batch in result]
    if len(result) == 1:
        [batch] = result
        rows = _db.select(
            'SELECT job.*, pg_temp.job_runs(job.cmdline) AS runs '
            'FROM job '
            'JOIN batch_job ON job.cmdline = batch_job.job '
            'WHERE batch_job.batch = %(cmdline)s '
            ';', {
                'cmdline': json.dumps(batch['cmdline']),
                })
        jobs = [
            {
                **row,
                'other_tags': sorted(
                    t
                    for t in row['tags']
                    if not t.startswith('dir:')
                    if '/' + t + '/' not in row['cmdline']['args']
                    ),
                'history_url': url_for(
                    'list_runs',
                    **row['cmdline'],
                    ),
                'cmdline_script': _cmdline_to_str(row['cmdline']),
                }
            for row in rows
            ]
        _sort_jobs(jobs, order)
        if not request.accept_mimetypes.accept_html:
            return jsonify(jobs)
        else:
            return render_template(
                'batch_list.html',
                batches=[batch | {
                    'cmdline_script': _cmdline_to_str(batch['cmdline']),
                    }],
                date_filter=date_filter,
                jobs=jobs,
                )
    else:
        if not request.accept_mimetypes.accept_html:
            return jsonify(result)
        else:
            return render_template(
                'batch_list.html',
                batches=result,
                date_filter=date_filter,
                )


def _cmdline_to_str(cmdline: Mapping[str, str]) -> str:
    # Environment variables are not a part of terminal command.
    opt = [
        key.removeprefix('opt.') + '=' + shlex.quote(value)
        for key, value in cmdline.items()
        if key.startswith('opt.')
        ]
    result = [cmdline.get('exe', ''), cmdline.get('args', ''), *opt]
    return ' '.join(result)


def _sort_jobs(jobs: List[Mapping[str, str]], order: str):
    """Sort by given strategy. Rely on stability of sort()."""
    jobs.sort(key=lambda j: j['cmdline']['args'])
    if order == 'name':
        return
    jobs.sort(reverse=True, key=_extent_of_interest)
    if order == 'pending':
        return
    jobs.sort(reverse=True, key=_extent_of_failure)


def _extent_of_failure(job):
    return job['status'] == 'failed', len(job['runs'])


def _extent_of_interest(job):
    order = ('failed', 'skipped', 'passed')  # Unknown values are to the left.
    status = job['status']
    # Greater values mean more "interest". Unknowns get max score.
    return -(order.index(status) if status in order else -1)


@batches_blueprint.route('/batches/jobs/schedule', methods=['POST'])
@_reraise_on_db_write_error
def _schedule_single_job():
    form = {**request.form}
    _logger.debug("Update job %s progress: %s", form, queued_progress('high'))
    _db.perform(
        'pg_temp.job_update_status',
        queued_progress('high'),
        'pending',
        json.dumps(form),
        )
    return _redirect_back()


def queued_progress(priority: str) -> str:
    # Values are arbitrary and intentionally different from values from
    # priority values used in other components.
    value = {'low': 70, 'high': 30}.get(priority, 50)
    return f'queued_{value}_{datetime.utcnow().isoformat(timespec="microseconds")}'


@batches_blueprint.route('/batches/jobs/recalculate', methods=['POST'])
@_reraise_on_db_write_error
def _batch_recalculate():
    form = {**request.form}
    _db.perform('pg_temp.batch_counters_update', json.dumps(form))
    return _redirect_back()
