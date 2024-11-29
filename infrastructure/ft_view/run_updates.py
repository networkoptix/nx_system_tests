# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging.config
import shlex
import time
from pathlib import Path

from infrastructure._message_broker_config import get_service_client
from infrastructure._uri import get_group_uri
from infrastructure._uri import get_process_uri
from infrastructure.ft_view import _db
from infrastructure.ft_view._enrichment import enrich
from infrastructure.ft_view._enrichment import enrich_with_ticket

_logger = logging.getLogger(__name__)


def main():
    consumer = get_service_client().get_consumer(
        'ft:run_updates', get_group_uri(), get_process_uri())
    _db.execute(Path(__file__).with_name('run_index.sql').read_text())
    _db.execute(Path(__file__).with_name('job_status_update.sql').read_text())
    _db.execute(Path(__file__).with_name('run_updates.sql').read_text())
    while True:
        message_raw = consumer.read_message()
        if message_raw is not None:
            message = json.loads(message_raw)
            _logger.info("Update stage: %r", message)
            data = {
                **message['run_cmdline'],
                'proc.username': message['run_username'],
                'proc.hostname': message['run_hostname'],
                'proc.started_at': message['run_started_at_iso'],
                'proc.pid': message['run_pid'],
                'report.duration_sec': message.get('stage_duration_sec'),
                'report.status': message['stage_status'],
                'report.run_url': message.get('run_url'),
                }
            enrich(data)
            enrich_with_ticket(data, message.get('stage_message'))
            _db.perform('pg_temp.store_update', json.dumps({
                'run_message': _avoid_zero_symbol(message.get('stage_message')),
                'run_cmdline': message['run_cmdline'],
                'artifact_urls': message.get('artifact_urls', []),
                'run_args': _pytest_style_test_name(message['run_cmdline']['args']),
                'run_data': data,
                }))
            # Message must not be acknowledged on unhandled exceptions.
            consumer.acknowledge()
        time.sleep(0.01)


def _pytest_style_test_name(args):
    """Make run_args value in the old style (like in pytest).

    >>> _pytest_style_test_name('-m tests.test_foo test_bar')
    'tests/test_foo.py::test_bar'
    >>> _pytest_style_test_name('-m suites.gui.test_foo')
    'suites/gui/test_foo.py'
    """
    args = shlex.split(args)
    if args[0] != '-m':
        raise ValueError(f"Args {args!r} must start with '-m'")
    args = args[1:]
    args[0] = args[0].replace('.', '/')
    args[0] = args[0] + '.py'
    args = '::'.join(args)
    return args


def _avoid_zero_symbol(message: str):
    if message:
        # Postgres JSONB format does not support \0 symbols.
        # Trying to convert string to JSONB format fails with error
        # DETAIL:  \u0000 cannot be converted to text.
        return message.replace('\0', '\u2400')
    else:
        return None


if __name__ == '__main__':
    log_dir = Path('~/.cache/ft_view_logs').expanduser()
    log_dir.mkdir(exist_ok=True, parents=False)
    log_file = log_dir / 'run_updates.log'
    logging.getLogger().setLevel(logging.DEBUG)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=200 * 1024**2, backupCount=6)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(stream_handler)
    main()
