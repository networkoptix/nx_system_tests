# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
import urllib.parse
from collections import defaultdict
from contextlib import contextmanager
from functools import lru_cache
from ipaddress import ip_network
from uuid import UUID

import requests

from mediaserver_api import StatisticsReport
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types

_logger = logging.getLogger(__name__)


@contextmanager
def statserver_configured(artifacts_dir):
    network = ip_network('10.254.10.0/28')
    vm_pool = public_default_vm_pool(artifacts_dir)
    with vm_pool.clean_vm(vm_types['statserver']) as vm:
        vm.os_access.wait_ready()
        statserver = _StatisticsServer(vm, network)
        statserver.stop()
        statserver.pull_latest_version()
        statserver.clean_web_dir()
        statserver.start()
        statserver.clean_up()
        yield _StatserverStand(statserver, vm, network)
        statserver.collect_logs(artifacts_dir)
        statserver.stop()


class _StatserverStand:

    def __init__(self, statserver, vm, network):
        self._statserver = statserver
        self._vm = vm
        self._network = network

    def statserver(self):
        return self._statserver

    def vm(self):
        return self._vm

    def subnet(self):
        return self._network


class _StatisticsServer:
    # Values are hard-coded in statserver VM image.
    _user = 'statlord'  # noqa SpellCheckingInspection
    _password = 'razdvatri'  # noqa SpellCheckingInspection
    _request_ip_addr = '127.0.0.1'
    _port = 8008

    def __init__(self, vm, internal_network):
        self._os_access = vm.os_access
        self._internal_network = internal_network
        # Statserver URL to make SQL request from host where test runs
        request_port = self._os_access.get_port('tcp', self._port)
        self._request_url = (
            f'http://{self._user}:{self._password}@'
            f'{self._request_ip_addr}:{request_port}'
            '/statserver/api/sqlFormat')
        self._mediaserver_records = defaultdict(list)
        self._service_name = 'statserver'
        self._service = self._os_access.service(self._service_name)

    @property
    @lru_cache()
    def url(self) -> str:
        # Statserver URL to add it to Mediaserver
        [ip_addr] = self._os_access.networking.get_ip_addresses_within_subnet(self._internal_network)
        ip_addr = ip_addr.ip
        return f'http://{ip_addr}:{self._port}'

    def _make_sql_request(self, sql_request):
        _logger.info("Trying to get response for query %s", sql_request)
        sql_request = urllib.parse.quote(sql_request)
        response = requests.get(f'{self._request_url}/{sql_request}')
        _logger.info(
            "Response: HTTP %s %s; %r", response.status_code, response.reason, response.content)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            raise RuntimeError(
                f"Response for {response.request.url} is not a JSON; "
                f"Response:\n{response.content}")

    @staticmethod
    def _make_record(record):
        public_ip = record['etc'].get('publicIp', '')
        if 'hddList' in record['etc']:
            hdd_list = [hdd.strip() for hdd in record['etc']['hddList'].split(',')]
        else:
            hdd_list = []
        backup_start = record.get('backupStart')
        if backup_start is None:
            backup_start = 0
        backup_bitrate_bps = record.get('backupBitrateBytesPerSecond')
        if backup_bitrate_bps is None:
            backup_bitrate_bps = []
        return StatisticsReport(
            id=UUID(record['id']),
            system_id=UUID(record['systemId']),
            parent_id=UUID(record['etc']['parentId']),
            plugin_info=record['etc']['pluginInfo'],
            hdd_list=hdd_list,
            physical_memory=int(record['etc']['physicalMemory']),
            product_name=record['etc']['productNameShort'],
            public_ip=public_ip,
            publication_type=record['etc']['publicationType'],
            cpu_architecture=record['cpuArchitecture'],
            cpu_model=record['cpuModelName'],
            flags=set(record['flags'].split('|')),
            full_version=record['fullVersion'],
            max_cameras=record['maxCameras'],
            status=record['status'],
            system_runtime=record['systemRuntime'],
            version=record['version'],
            backup_start=backup_start,
            backup_type=record.get('backupType'),
            backup_days_of_week=record['etc'].get('backupDaysOfTheWeek'),
            backup_duration=record.get('backupDuration'),
            backup_bitrate=record.get('backupBitrate'),
            backup_bitrate_bps=backup_bitrate_bps,
            )

    def get_new_mediaserver_records(self, mediaserver_id, timeout_sec=10):
        started = time.monotonic()
        existing_records = self._mediaserver_records[mediaserver_id]
        while time.monotonic() - started < timeout_sec:
            records = self._make_sql_request(
                f'SELECT * FROM mediaservers WHERE id="{{{mediaserver_id}}}"')
            new_records = []
            for r in records:
                record = self._make_record(r)
                if record not in existing_records:
                    new_records.append(record)
            if new_records:
                existing_records.extend(new_records)
                return new_records
            time.sleep(1)
        else:
            raise RuntimeError(
                f"Failed to get new records for {mediaserver_id} after {timeout_sec} seconds")

    def _wait_for_server_online(self):
        timeout_sec = 40
        started = time.monotonic()
        while time.monotonic() - started < timeout_sec:
            try:
                self._make_sql_request('SHOW TABLES')
            except requests.ConnectionError:
                pass  # Server is not started yet.
            except requests.HTTPError as exc:
                # After start server can return 502 Bad Gateway for some time.
                if exc.response.status_code != 502:
                    raise
            else:
                break
            time.sleep(1)
        else:
            raise RuntimeError(
                f"Statistics server is not online after {timeout_sec} seconds")

    def clean_up(self):
        self._make_sql_request('DELETE FROM mediaservers')

    def start(self):
        self._service.start()
        self._wait_for_server_online()

    def stop(self):
        if self._service.status().is_stopped:
            return
        self._service.stop()

    def pull_latest_version(self):
        self._os_access.run(
            command=['docker-compose', '-f', '/statserver/docker-compose.yml', 'pull'],
            timeout_sec=180,  # On CI machines, this may take longer than usual
            )

    def clean_web_dir(self):
        stat_web_dir = self._os_access.path('/statserver/web')
        stat_web_dir.rmtree(ignore_errors=True)
        stat_web_dir.mkdir()

    def collect_logs(self, artifacts_dir):
        command = f'journalctl --output short-precise --no-pager -u {self._service_name}'
        outcome = self._os_access.run(command)
        artifacts_dir.joinpath('statserver-service.log').write_bytes(outcome.stdout)
