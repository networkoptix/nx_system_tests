# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging.config
import subprocess
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from flask import Flask
from flask import g
from flask import redirect
from flask import request
from flask import url_for
from jinja2 import FileSystemBytecodeCache
from jinja2 import StrictUndefined

from infrastructure.ft_view import _db
from infrastructure.ft_view._enrichment import day_match_tz
from infrastructure.ft_view._enrichment import period_keys
from infrastructure.ft_view.web_ui._batches_blueprint import _list
from infrastructure.ft_view.web_ui._batches_blueprint import batches_blueprint
from infrastructure.ft_view.web_ui._locations import run_locations
from infrastructure.ft_view.web_ui._runs import list_runs_view
from infrastructure.ft_view.web_ui._runs import run_stats
from infrastructure.ft_view.web_ui._tickets_api import tickets_blueprint
from infrastructure.ft_view.web_ui._unique_random_icons import unique_random_icon
from infrastructure.ft_view.web_ui._urls import ObsoleteURL
from infrastructure.ft_view.web_ui._urls import URLParamSet
from infrastructure.ft_view.web_ui._urls import query_string

log_dir = Path('~/.cache/ft_view_logs').expanduser()
log_dir.parent.mkdir(exist_ok=True, parents=False)
log_dir.mkdir(exist_ok=True, parents=False)
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        # Flask may fork. E.g. for code reload.
        # When forked, process names stay the same. Hence, the id is logged.
        # Threads are named uniquely by Python. Hence, the name is logged.
        'stream': {
            'format': '%(process)d:%(threadName)s:' + logging.BASIC_FORMAT,
            },
        'file': {
            'format': '%(asctime)s %(process)d %(threadName)s %(name)s %(levelname)s %(message)s',
            },
        },
    'handlers': {
        'stream': {
            'level': 'INFO',
            'formatter': 'stream',
            'class': 'logging.StreamHandler',
            },
        'file': {
            'level': 'DEBUG',
            'formatter': 'file',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(log_dir / f'{__name__}.log'),
            'maxBytes': 200 * 1024**2,
            'backupCount': 6,
            },
        },
    'loggers': {
        '': {
            'handlers': ['stream', 'file'],
            'level': 'DEBUG',
            },
        'waitress.queue': {'level': 'ERROR'},
        'urllib3.connectionpool': {'level': 'INFO'},
        },
    })


app = Flask(__name__)
app.config['SECRET_KEY'] = 'WellKnownPassword2'
app.jinja_env.undefined = StrictUndefined
app.jinja_env.bytecode_cache = FileSystemBytecodeCache()
app.jinja_env.globals |= {
    'request_params': lambda: URLParamSet.from_flask(request.args, {min(period_keys(g.today)): ''}),
    query_string.__name__: query_string,
    '_run_id': lambda run_data: {
        'proc.username': run_data['proc.username'],
        'proc.hostname': run_data['proc.hostname'],
        'proc.started_at': run_data['proc.started_at'],
        'proc.pid': run_data['proc.pid'],
        },
    'last_line': lambda s: '' if not s else s.rstrip().rsplit('\n', 1)[-1],
    }
app.add_url_rule('/locations/', 'index', run_locations)
app.add_url_rule('/runs/', 'list_runs', list_runs_view)
app.add_url_rule('/stats/', run_stats.__name__, run_stats)

_started_at = time.monotonic()
try:
    _tz = ZoneInfo('CET')  # TODO: Make configurable by user
except ZoneInfoNotFoundError:
    _tz = timezone.utc
# Ignore exit code. Show stderr in UI too.
_git_commit = subprocess.getoutput('git log -1 --format=format:"%cI %h %ce"')
_git_sha = subprocess.getoutput('git rev-parse HEAD')
app.context_processor(lambda: {
    'time_zone': _tz,
    'uptime': timedelta(seconds=int(time.monotonic() - _started_at)),
    'ft_view_git': _git_commit,
    'static_version': _git_sha,
    unique_random_icon.__name__: unique_random_icon,
    'strftime': lambda t, f: datetime.fromisoformat(t).astimezone(_tz).strftime(f),
    })

app.register_blueprint(batches_blueprint)
app.register_blueprint(tickets_blueprint)
_db.execute(Path(__file__).parent.with_name('run_index.sql').read_text(), read_only=True)
_db.execute(Path(__file__).parent.with_name('job_status_update.sql').read_text())
_db.execute(Path(__file__).parent.with_name('batches_api.sql').read_text())
_db.execute(Path(__file__).parent.with_name('web_ui.sql').read_text(), read_only=True)


@app.before_request
def _set_request_date():
    g.today = datetime.now(tz=day_match_tz).date()


@app.errorhandler(ObsoleteURL)
def _handle_obsolete_url(error: ObsoleteURL):
    return redirect(error.updated_url)


@app.route('/failures/')
def _similar_failures_redirect():
    query = {}
    for k, v in request.args.items():
        if k == 'test_id' or k == 'args':
            if v.startswith(('tests/', 'suites/')):
                query['args'] = '-m ' + v.replace('.py', '').replace('::', ' ').replace('/', '.')
            else:
                query['args'] = v
        else:
            query[k] = v
    return redirect('/runs/' + query_string(**query))


@app.route('/runs/<username>/<hostname>/<date>/<time>/', defaults={'prefix': None})
@app.route('/runs/<username>/<hostname>/<date>/<time>/::<path:prefix>')
def _get_run_redirect(username, hostname, date, time, prefix):
    return redirect(
        url_for(
            'list_runs',
            username=username,
            hostname=hostname,
            started_at=date + 'T' + time,
            ),
        )


@app.route('/runs/<username>/<hostname>/<started_at>/')
@app.route('/runs/<username>/<hostname>/<started_at>/::<path:prefix>')
def _get_run_to_list_runs_redirect(username, hostname, started_at, prefix=None):
    return redirect(
        url_for(
            'list_runs',
            username=username,
            hostname=hostname,
            started_at=started_at,
            ),
        )


@app.route('/batches/jobs')
def _get_batch_redirect():
    return redirect(
        url_for(
            batches_blueprint.name + '.' + _list.__name__,
            **request.args,
            ),
        )


@app.route('/batches/')
@app.route('/batches')
@app.route('/batches/batches')  # Shortener malfunction.
def _batch_list_compatibility_redirect():
    return redirect(
        url_for(
            batches_blueprint.name + '.' + _list.__name__,
            **request.args,
            ),
        )
