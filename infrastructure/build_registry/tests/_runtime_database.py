# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping

from infrastructure.build_registry.builds_database import BuildsDatabase
from infrastructure.build_registry.builds_database import InvalidMetadataQuery


class RuntimeDatabase(BuildsDatabase):

    def __init__(self):
        self._store = []

    def add_build(self, metadata):
        self._store.append(metadata)

    def full_text_search(self, metadata: Mapping[str, str]):
        result = []
        for record in self._store[::-1]:
            if not self._match(record, metadata):
                continue
            result.append(record)
        return result

    def list_recent(self):
        return self._store[::-1]

    @staticmethod
    def _match(record, metadata) -> bool:
        for key, value in metadata.items():
            value_prefix, separator, rest = value.partition('*')
            if rest:
                raise InvalidMetadataQuery("Only single trailing asterisk is allowed for a wildcard search")
            match_string = f'{key}={value_prefix}'
            if separator:
                if not any(line.startswith(match_string) for line in record.splitlines()):
                    return False
            else:
                if match_string not in record.splitlines():
                    return False
        return True

    def close(self):
        pass
