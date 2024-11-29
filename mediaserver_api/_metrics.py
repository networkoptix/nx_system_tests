# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import re
from collections import namedtuple
from datetime import datetime
from uuid import UUID


class MetricsValues:

    @staticmethod
    def _make_dict(kwargs):
        return {key: value for key, value in kwargs.items() if value is not None}

    @staticmethod
    def make_system_info(
            servers=1,
            cameras=0,
            users=1,
            storages=1,
            ):
        return MetricsValues._make_dict(dict(
            servers=servers,
            cameras=cameras,
            users=users,
            storages=storages,
            ))

    @staticmethod
    def make_storages(
            status='Inaccessible',
            total_bytes=None,
            used_bytes=None,
            used_ratio=None,
            server_id=None,
            type='local',
            location=None,
            read_bytes_per_sec=None,
            write_bytes_per_sec=None,
            transactions_per_sec=None,
            ):
        return MetricsValues._make_dict(dict(
            status=status,
            total_bytes=total_bytes,
            used_bytes=used_bytes,
            used_ratio=used_ratio,
            server_id=server_id,
            type=type,
            location=location,
            read_bytes_per_sec=read_bytes_per_sec,
            write_bytes_per_sec=write_bytes_per_sec,
            transactions_per_sec=transactions_per_sec,
            ))

    @staticmethod
    def make_cameras(
            archive_length_sec=None,
            min_archive_length_sec=None,
            type=None,
            ip_address=None,
            model=None,
            firmware=None,
            vendor=None,
            primary=None,
            secondary=None,
            status=None,
            ):
        return MetricsValues._make_dict(dict(
            archive_length_sec=archive_length_sec,
            min_archive_length_sec=min_archive_length_sec,
            type=type,
            ip_address=ip_address,
            model=model,
            firmware=firmware,
            vendor=vendor,
            primary=primary,
            secondary=secondary,
            status=status,
            ))

    @staticmethod
    def _camera_stream(stream_params):
        bitrate = stream_params.get('actualBitrateBps')

        try:
            bitrate_kbps = bitrate / 1000 * 8
        except TypeError:
            bitrate_kbps = None

        return MetricsValues._make_dict(dict(
            bitrate_kbps=bitrate_kbps,
            actual_fps=stream_params.get('actualFps'),
            target_fps=stream_params.get('targetFps'),
            resolution=stream_params.get('resolution'),
            ))

    def __init__(self, raw_data):
        self._data = raw_data
        self._site_term = 'systems' if 'systems' in self._data else 'sites'

    def get_metrics(self, resource_type, *metric_path):
        try:
            metrics = getattr(self, resource_type)()
        except AttributeError:
            raise RuntimeError(f"There is no {resource_type}-level metrics")
        while metric_path:
            current, *metric_path = metric_path
            try:
                metrics = metrics[current]
            except KeyError:
                return None
        return metrics

    def list_of_dicts_with_known_keys(self):
        result = []
        # TODO: Is there exactly one system? What connects server and system?
        [system_id] = self._data[self._site_term].keys()
        system_name = self._data[self._site_term][system_id]['info']['name']
        server_names = {
            server_id: server_data['_']['name']
            for server_id, server_data in self._data['servers'].items()
            }
        for resource_type, resources in self._data.items():
            for resource_id, resource_metrics in resources.items():
                if resource_type == self._site_term:
                    server_id = None
                    server_name = None
                else:
                    if resource_type == 'servers':
                        server_id = resource_id
                    else:
                        server_id = resource_metrics['info']['server']
                    server_name = server_names[server_id]
                enriched = {
                    'site': {
                        'id': system_id,
                        'name': system_name,
                        },
                    'server': {
                        'id': server_id,
                        'name': server_name,
                        },
                    'resource': {
                        'type': resource_type,
                        'id': resource_id,
                        'metrics': resource_metrics,
                        },
                    }
                result.append(enriched)
        return result

    def system_info(self):
        [only_system] = self._data[self._site_term].values()
        system_info_dict = only_system['info']
        return self._make_dict({
            k: system_info_dict.get(k)
            for k in ('servers', 'cameras', 'users', 'storages')})

    def storages(self):
        storages = {}
        for s_id, metrics in self._data['storages'].items():
            space = metrics.get('space', {})
            info = metrics.get('info', {})
            activity = metrics.get('activity', {})
            storages[UUID(s_id)] = self._make_dict(dict(
                status=metrics.get('state', {}).get('status'),
                total_bytes=space.get('totalSpaceB'),
                used_bytes=space.get('mediaSpaceB'),
                used_ratio=space.get('mediaSpaceP'),
                server_id=UUID(info['server']) if 'server' in info else None,
                type=info.get('type'),
                location=metrics.get('_', {}).get('name'),
                read_bytes_per_sec=activity.get('readRateBps1m'),
                write_bytes_per_sec=activity.get('writeRateBps1m'),
                transactions_per_sec=activity.get('transactionsPerSecond'),
                ))
        return storages

    def cameras(self):
        cameras = {}
        for camera_id, metrics in self._data['cameras'].items():
            storage = metrics.get('storage', {})
            info = metrics.get('info', {})
            primary = None
            secondary = None
            if 'primaryStream' in metrics:
                primary = self._camera_stream(metrics['primaryStream'])
            if 'secondaryStream' in metrics:
                secondary = self._camera_stream(metrics['secondaryStream'])
            cameras[UUID(camera_id)] = self._make_dict(dict(
                archive_length_sec=storage.get('archiveLengthS'),
                min_archive_length_sec=storage.get('minArchiveLengthS'),
                type=info.get('type'),
                ip_address=info.get('ip'),
                model=info.get('model'),
                firmware=info.get('firmware'),
                vendor=info['vendor'].lower() if 'vendor' in info else None,
                primary=primary,
                secondary=secondary,
                status=metrics.get('availability', {}).get('status'),
                ))
        return cameras

    @staticmethod
    def _rates(rates):
        # Mediaserver design allows having missing
        # keys from the metrics dict, even if rates key is present.
        # See: VMS-30096

        return dict(
            in_kbit=rates['inBps1m'] / 1000 * 8 if 'inBps1m' in rates else None,
            out_kbit=rates['outBps1m'] / 1000 * 8 if 'outBps1m' in rates else None,
            )

    def network_interfaces(self):
        interfaces = {}
        # Interfaces keys are server_id + interface name
        for interface in self._data['networkInterfaces'].values():
            server_id = UUID(interface['info']['server'])
            name = interface['_']['name']
            interfaces[(server_id, name)] = self._make_dict(dict(
                name=name,
                state=interface['info'].get('state'),
                display_address=interface['info'].get('displayAddress'),
                other_addresses=interface['info'].get('otherAddresses'),
                rates=self._rates(interface['rates']) if 'rates' in interface else None,
                ))
        return interfaces

    @staticmethod
    def _parse_time(metrics_time) -> datetime:
        try:
            # The datetime is formatted as ISO 8601 in APIv4.
            return datetime.fromisoformat(metrics_time)
        except ValueError:
            pass
        # In APIv3 and below, the datetime has own format.
        match = re.fullmatch(
            r'(?P<date>\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d) '
            r'\(UTC (?P<sign>[+-])(?P<hours>\d{1,2})(?P<minutes>|15|30|45)\)',
            metrics_time)
        if match is None:
            raise RuntimeError(f"Failed to parse {metrics_time!r}")
        date = match.group('date')
        sign = match.group('sign')
        hours = match.group('hours').rjust(2, '0')
        minutes = match.group('minutes').rjust(2, '0')
        return datetime.fromisoformat(date + sign + hours + ':' + minutes)

    def servers(self):
        servers = {}
        for server_id, data in self._data['servers'].items():
            load = data.get('load', {})
            info = data.get('info', {})
            vms_time = self._parse_time(info['vmsTime']) if 'vmsTime' in info else None
            os_time = self._parse_time(info['osTime']) if 'osTime' in info else None
            servers[UUID(server_id)] = self._make_dict(dict(
                decoding_threads=load.get('decodingThreads'),
                decoding_speed_pix=load.get('decodingSpeed3s'),
                encoding_threads=load.get('encodingThreads'),
                encoding_speed_pix=load.get('encodingSpeed3s'),
                primary_streams=load.get('primaryStreams'),
                secondary_streams=load.get('secondaryStreams'),
                cameras=load.get('cameras'),
                time_changed_24h=info.get('vmsTimeChanged24h'),
                offline_events=data.get('availability', {}).get('offlineEvents'),
                vms_time=vms_time,
                os_time=os_time,
                transactions_per_sec=data.get('activity', {}).get('transactionsPerSecond1m'),
                cpu=info.get('cpu'),
                threads=load.get('threads'),
                total_cpu_usage=load.get('cpuUsageP'),
                vms_cpu_usage=load.get('serverCpuUsageP'),
                total_ram_usage=load.get('ramUsageP'),
                vms_ram_usage=load.get('serverRamUsageP'),
                total_ram_usage_bytes=load.get('ramUsageB'),
                # In 5.0 field got renamed to serverRamUsageB
                vms_ram_usage_bytes=load.get('serverRamUsage') or load.get('serverRamUsageB'),
                ))
        return servers


Alarm = namedtuple('Alarm', 'level text')
