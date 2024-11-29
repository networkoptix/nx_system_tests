# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sqlite3
import time
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from typing import Mapping
from typing import Optional
from typing import Sequence


class InvalidMetadataQuery(Exception):
    pass


class BuildsDatabase(metaclass=ABCMeta):

    @abstractmethod
    def add_build(self, metadata):
        pass

    @abstractmethod
    def full_text_search(
            self,
            metadata: Mapping[str, str]) -> Sequence[str]:
        pass

    @abstractmethod
    def list_recent(self) -> Sequence[str]:
        pass

    @abstractmethod
    def close(self):
        pass


def _init_builds_table(connection: sqlite3.Connection):
    connection.execute(
        'CREATE TABLE IF NOT EXISTS builds ('
        'creation_timestamp REAL NOT NULL, '
        'metadata TEXT NOT NULL);',
        )


def _init_builds_fts_table(connection: sqlite3.Connection):
    connection.execute(
        'CREATE VIRTUAL TABLE IF NOT EXISTS builds_fts USING fts5('
        'metadata, '
        'content=builds,'
        'tokenize=trigram);',  # Allows exact match. See: https://www.sqlite.org/fts5.html
        )


def _bound_fts_insert(connection: sqlite3.Connection):
    connection.execute(
        'CREATE TRIGGER IF NOT EXISTS builds_fts_insert AFTER INSERT ON builds '
        'BEGIN '
        'INSERT INTO builds_fts (rowid, metadata) '
        'VALUES (new.rowid, new.metadata); '
        'END;')


def _bound_fts_delete(connection: sqlite3.Connection):
    connection.execute(
        'CREATE TRIGGER IF NOT EXISTS builds_fts_delete AFTER DELETE ON builds '
        'BEGIN '
        'DELETE FROM builds_fts WHERE rowid = old.rowid; '
        'END;')


def _generate_metadata_expression(metadata_regexp: Mapping[str, str]) -> str:
    # Asterisk (*) is chosen as a wildcard symbol, because it is
    # commonly used this way. SQlite FTS treat expression as a prefix
    # if it is not terminated by \n and as a full match otherwise.
    search_expression_parts = []
    for key, value in metadata_regexp.items():
        value_prefix, separator, rest = value.partition('*')
        if rest:
            raise InvalidMetadataQuery("Only single trailing asterisk is allowed for a wildcard search.")
        if separator:
            search_expression_part = f'{key}={value_prefix}'
        else:
            search_expression_part = f'{key}={value}\n'
        search_expression_parts.append(search_expression_part)
    return ' AND '.join(_quote_fts_string(part) for part in search_expression_parts)


def _quote_fts_string(s):
    """Escape double quotes SQL-style for FTS phrase."""
    # See: https://www.sqlite.org/fts5.html#fts5_strings
    return '"' + s.replace('"', '""') + '"'


class SqliteLastUsageDatabase(BuildsDatabase):

    # Enables autocommit mode meaning `one changing data statement` == `one transaction`
    # See: https://docs.python.org/3/library/sqlite3.html?highlight=isolation_level#transaction-control
    _isolation_level = None

    def __init__(self, db_file: Path):
        self._db_file = db_file
        self._db_connection: Optional[sqlite3.Connection] = None

    def add_build(self, metadata):
        query = (
            'INSERT INTO builds VALUES ( '
            ':creation_timestamp, '
            ':metadata);'
            )
        start_at = time.monotonic()
        self._get_connection().execute(
            query,
            {
                'creation_timestamp': datetime.now(tz=timezone.utc).timestamp(),
                'metadata': metadata,
                },
            )
        time_spent = time.monotonic() - start_at
        logging.info(
            "Query '%s' with parameters '%s' took %.6f sec to execute",
            query, metadata, time_spent)

    def full_text_search(self, metadata: Mapping[str, str]):
        search_expression = f'metadata : {_generate_metadata_expression(metadata)}'
        logging.info("Generated metadata expression match '%s' from '%s'", metadata, metadata)
        logging.info("FTS match expression: '%s'", search_expression)
        query = (
            'SELECT metadata '
            'FROM builds '
            'WHERE rowid IN ('
            'SELECT rowid '
            'FROM builds_fts '
            'WHERE builds_fts MATCH :search_expression'
            ') '
            'ORDER BY rowid DESC '
            'LIMIT 1000;'
            )
        parameters = {'search_expression': search_expression}
        start_at = time.monotonic()
        cursor = self._get_connection().execute(query, parameters)
        result = [metadata for metadata, *_ in cursor]
        time_spent = time.monotonic() - start_at
        logging.info(
            "Query '%s' with parameters '%s' took %.6f sec to execute",
            query, parameters, time_spent)
        return result

    def list_recent(self):
        query = (
            'SELECT metadata '
            'FROM builds_fts '
            'ORDER BY rowid DESC '
            'LIMIT 1000;'
            )
        start_at = time.monotonic()
        cursor = self._get_connection().execute(query, {})
        result = [metadata for metadata, *_ in cursor]
        time_spent = time.monotonic() - start_at
        logging.info(
            "Query '%s' took %.6f sec to execute",
            query, time_spent)
        return result

    def _get_existing_connection(self) -> Optional[sqlite3.Connection]:
        try:
            return sqlite3.connect(
                f"file:{self._db_file}?mode=rw",
                uri=True,
                isolation_level=self._isolation_level)
        except sqlite3.OperationalError as err:
            if 'unable to open database file' not in str(err):
                raise
        return None

    @lru_cache(maxsize=1)
    def _get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_file, isolation_level=self._isolation_level)
        _init_builds_table(connection)
        _init_builds_fts_table(connection)
        _bound_fts_insert(connection)
        _bound_fts_delete(connection)
        return connection

    def close(self):
        self._get_connection().close()
        self._get_connection.cache_clear()
