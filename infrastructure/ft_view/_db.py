# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import List
from typing import Optional

import psycopg2
import psycopg2.extensions
from psycopg2.extras import MinTimeLoggingConnection
from psycopg2.extras import MinTimeLoggingCursor
from psycopg2.extras import RealDictCursor

from config import global_config

_logger = logging.getLogger(__name__)


class WriteForbiddenError(Exception):
    pass


class _Connection(MinTimeLoggingConnection):
    pass


class _Cursor(MinTimeLoggingCursor, RealDictCursor):
    pass


class _TreatAsWarningLoggingAdapter(logging.LoggerAdapter):

    def log(self, level, msg, *args, **kwargs):
        super().log(max(logging.WARNING, level), msg, *args, **kwargs)


_connections: List[Optional[_Connection]] = [None, None]


def _get_connection(*, read_only: bool):
    # It disconnects after idling for 10 minutes. Even with TCP keep-alive.
    # Perhaps, the Kubernetes networking does that.
    if _connections[read_only] is None:
        if read_only:
            user = global_config.get('pguser_read_only', 'ft_view_read_only')
        else:
            user = global_config.get('pguser', 'ft_view')
        try:
            host = global_config.get('pghost', '127.0.0.1')
            db = global_config.get('pgdatabase', 'ft_view')
            _logger.info("Connect to Postgres: %s:%s:5432:%s", host, db, user)
            _connections[read_only] = psycopg2.connect(
                connection_factory=_Connection,
                cursor_factory=_Cursor,
                host=host,
                dbname=db,
                user=user,
                # Password in ~/.pgpass or %APPDATA%\postgresql\pgpass.conf
                # (with chmod 0600 on Unix-like OS). Sample contents:
                # 127.0.0.1:5432:ft_view:ft_view:VeryStrongPassword
                # 127.0.0.1:5432:ft_view:ft_view_read_only:WellKnownPassword2
                # nxft.dev:5432:ft_view:ft_view_read_only:WellKnownPassword2
                # us.nxft.dev:5432:ft_view:ft_view_read_only:WellKnownPassword2
                # Customize via PGPASSFILE var or passfile connection param.
                # See: https://www.postgresql.org/docs/current/libpq-pgpass.html
                # In the production setup, it was seen that the peer or something
                # in between sent FIN when the connection idle for 60 or 600 sec.
                # See: https://www.postgresql.org/docs/current/libpq-connect.html
                keepalives=1,  # It's the default. Specified for clarity.
                keepalives_idle=10,  # On Windows and Linux the default is 2 hours.
                keepalives_interval=2,
                keepalives_count=4,
                )
            _connections[read_only].autocommit = True
            logger = _TreatAsWarningLoggingAdapter(_logger.getChild('long'))
            _connections[read_only].initialize(logger, 1000)
            latency_ms = _measure_latency(_connections[read_only])
            _connections[read_only].initialize(logger, latency_ms * 3 + 50)
        except psycopg2.OperationalError as e:
            # Password can be read from a password file. Whether a password for
            # writing role provided, is known after connection is attempted.
            if not read_only and 'no password supplied' in str(e):
                raise WriteForbiddenError(e)
            raise
    return _connections[read_only]


def _measure_latency(conn):
    started_at = time.perf_counter_ns()
    with conn.cursor() as cursor:
        cursor.execute('SELECT 1;')
        cursor.fetchall()
    latency_ms = (time.perf_counter_ns() - started_at) / 1e6
    _logger.info("DB latency: %.3f ms", latency_ms)
    return latency_ms


def execute(sql, read_only=False):
    with _get_connection(read_only=read_only).cursor() as cursor:
        cursor.execute(sql)


def perform(func, *args):
    with _get_connection(read_only=False).cursor() as cursor:
        cursor.callproc(func, args)
        return cursor.fetchone()


def select(query, params=None):
    with _get_connection(read_only=True).cursor() as cursor:
        cursor.execute(query, vars=params)
        return cursor.fetchall()


def select_one(query, params):
    rows = select(query, params=params)
    if not rows:
        return None
    [row] = rows
    return row


def write(query, params):
    with _get_connection(read_only=False).cursor() as cursor:
        cursor.execute(query, vars=params)
        return cursor.rowcount


def write_returning(query, params):
    with _get_connection(read_only=False).cursor() as cursor:
        cursor.execute(query, vars=params)
        return cursor.fetchall()
