# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re
import time
from collections import namedtuple

_LogLevel = namedtuple('_LogLevel', ['severity', 'log_file', 'api_request'])


# From libs/nx_utils/src/nx/utils/log/log_level.h
class LevelEnum:
    VERBOSE = _LogLevel(1, 'VERBOSE', 'DEBUG2')
    DEBUG = _LogLevel(2, 'DEBUG', 'DEBUG')
    INFO = _LogLevel(3, 'INFO', 'INFO')
    WARNING = _LogLevel(4, 'WARNING', 'WARNING')
    ERROR = _LogLevel(5, 'ERROR', 'ERROR')
    ALWAYS = _LogLevel(6, 'ALWAYS', 'ALWAYS')

    @classmethod
    def from_string(cls, level):
        # severity == 0 is used to detect entries with unexpected levels
        return cls.__dict__.get(level, _LogLevel(0, level, level))


class _LogEntry:

    def __init__(self, timestamp, thread, level, tag, message):
        self.timestamp = timestamp
        self.thread = thread
        self.level = LevelEnum.from_string(level)
        self.tag = tag
        self.message = message

    def __repr__(self):
        return '<{} {} {}>'.format(
            self.timestamp,
            self.level.log_file,
            self.message,
            )


def get_log_entries(mediaserver):
    entries = []
    with mediaserver.downloaded_log_files('main*.log*') as log_files:
        for file in log_files:
            # `utf-8-sig` encoding is used to skip BOM bytes on decoding.
            content = file.read_text(encoding='utf-8-sig')
            for metadata_match, message_end in _iter_log_entries(content):
                message_begin = metadata_match.end()
                message = content[message_begin:message_end]
                match_dict = metadata_match.groupdict()
                entries.append(_LogEntry(**match_dict, message=message))
    return entries


def _iter_log_entries(content):
    log_entry_re = re.compile(
        r'''
        ^
        (?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})\s+
        (?P<thread>[0-9A-Fa-f]+)\s+  # Hex on Windows, decimal on Linux.
        (?P<level>[A-Z]{4,7})\s+
        (?P<tag>\S+):\s+
        ''',
        re.VERBOSE | re.MULTILINE,
        )

    match_iter = log_entry_re.finditer(content)
    match = next(match_iter)
    for next_match in match_iter:
        yield match, next_match.start()
        match = next_match
    yield match, None


def less_severe_entries(entries, severity):
    return [entry for entry in entries if entry.level.severity < severity]


def setup_server_and_trigger_logs(server, log_level):
    # Emulate "corrupted" database to raise an ERROR entry in the
    # mediaserver main log. It causes an assertion error before VMS-15425.
    server.ecs_db.write_bytes(b'0000')
    server.set_main_log_level(log_level)
    server.start()
    server.api.set_credentials('admin', 'admin')
    server.api.setup_local_system()
    api_log_level = server.api.http_get('api/logLevel', params={'id': 0})
    entries = get_log_entries(server)
    assert entries
    server.stop()
    time.sleep(1)  # To avoid mediaserver fast restart error
    for file in server.list_log_files('main*.log*'):
        file.unlink()
    return api_log_level, entries
