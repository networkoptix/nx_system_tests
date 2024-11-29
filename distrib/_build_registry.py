# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import json
from typing import Mapping
from typing import Sequence
from typing import Tuple
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen


class BuildRegistry:

    def __init__(self, build_registry_url: str):
        self._root_url = build_registry_url.rstrip('/') + '/'
        self._builds_url = self._root_url + 'builds'

    def list_builds_by_sha(self, sha: str) -> Sequence['BuildRecord']:
        return self._get({'GIT_COMMIT': sha})

    def get_stable_build(self, branch: str) -> 'BuildRecord':
        # Stable VMS build is chosen based on succeeded pipeline,
        # which means that installers and snapshots required for tests exist.
        # If branch has no new commits for a while -
        # then snapshots will be reused and should not get deleted by clean up script.
        # Checks for snapshot and installer existence can be safely removed.
        records = self._get({'ft:vms_stable': 'true', 'branch': branch})
        if not records:
            raise RuntimeError(f"Stable build is not found for branch {branch}")
        [latest_record, *_] = records
        return latest_record

    def add_record(self, record: str):
        request = Request(url=self._builds_url, method='POST', data=record.encode('utf8'))
        urlopen(request, timeout=10)

    def list_builds_with_snapshot(
            self,
            plugin_id: str,
            os_name: str,
            snapshot_creator: str,
            ) -> Sequence['BuildRecord']:
        return self._get({
            'ft:os_name': os_name,
            'ft:plugin_id': plugin_id,
            'ft:snapshot_creator': snapshot_creator,
            })

    def _get(self, query: Mapping[str, str]) -> Sequence['BuildRecord']:
        query = '?' + urlencode(query)
        with urlopen(self._builds_url + query, timeout=10) as response:
            data = response.read()
        return [BuildRecord(raw) for raw in json.loads(data)]


class BuildRecord:

    def __init__(self, build_record_raw: str):
        self._raw = build_record_raw
        self._as_dict = dict(line.split('=', 1) for line in self._raw.splitlines() if line)

    def build_is_stable(self) -> bool:
        return self._as_dict.get('ft:vms_stable') == 'true'

    def distrib_url(self) -> str:
        return self._as_dict['ft:url']

    def disks_urls(self) -> Tuple[str, str]:
        return self._as_dict['ft:root_disk_url'], self._as_dict['ft:mediaserver_disk_url']

    def with_stable_mark(self) -> 'BuildRecord':
        return self.__class__('\n'.join([*self._raw.splitlines(), 'ft:vms_stable=true']) + '\n')

    def with_snapshot(
            self,
            plugin_id: str,
            os_name: str,
            root_disk_url: str,
            mediaserver_disk_url: str,
            ) -> 'BuildRecord':
        return self.__class__('\n'.join([
            *self._raw.splitlines(),
            f'ft:os_name={os_name}',
            'ft:arch=x64',
            f'ft:plugin_id={plugin_id}',
            f'ft:snapshot_creator={getpass.getuser()}',
            f'ft:root_disk_url={root_disk_url}',
            f'ft:mediaserver_disk_url={mediaserver_disk_url}',
            ]) + '\n')

    def raw(self) -> str:
        return self._raw
