# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from typing import Sequence
from typing import Tuple

from directories.prerequisites import PrerequisiteStore
from doubles.video.ffprobe import SampleMediaFile
from os_access import OsAccess
from os_access import RemotePath
from os_access import copy_file

_logger = logging.getLogger(__name__)


def fetch_testcamera_sample_videos(
        prerequisite_store: PrerequisiteStore,
        ) -> Tuple[Path, Path]:
    high = prerequisite_store.fetch('test-cam/high.ts')
    low = prerequisite_store.fetch('test-cam/low.ts')
    # We are interested in their bitrate:
    _logger.info("Media sample: high: %s", SampleMediaFile(high))
    _logger.info("Media sample: low: %s", SampleMediaFile(low))
    return high, low


def upload_testcamera_sample_videos(
        local_sample_paths: Sequence[Path],
        vms_benchmark_os_access: OsAccess) -> Sequence[RemotePath]:
    remote_sample_paths = [
        vms_benchmark_os_access.home() / local_path.name
        for local_path in local_sample_paths
        ]
    for local_path, remote_path in zip(local_sample_paths, remote_sample_paths):
        copy_file(local_path, remote_path)
    return remote_sample_paths


def layout_for_testcamera(network):
    return {
        'machines': [
            dict(alias='test_camera', type='ubuntu22'),
            dict(alias='server_0', type='ubuntu22'),
            dict(alias='server_1', type='ubuntu22'),
            dict(alias='server_2', type='ubuntu22'),
            dict(alias='server_3', type='ubuntu22'),
            ],
        'networks': {
            str(network): {
                'test_camera': None,
                'server_0': None,
                'server_1': None,
                'server_2': None,
                'server_3': None,
                },
            },
        'mergers': [
            dict(local='server_0', remote='server_1', take_remote_settings=False, network=network),
            dict(local='server_0', remote='server_2', take_remote_settings=False, network=network),
            dict(local='server_0', remote='server_3', take_remote_settings=False, network=network),
            ],
        }
