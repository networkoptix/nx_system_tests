# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional
from typing import Sequence

from _internal.service_registry import gui_prerequisite_store
from doubles.video.ffprobe import SampleMediaFile
from installation import Mediaserver
from installation import TestCameraApp
from installation import TestCameraConfig
from installation import VmsBenchmarkInstallation
from mediaserver_api import Testcamera
from os_access import OsAccess
from os_access import copy_file


# TODO: The call to this function is often preceeded by a call to create_testcameras(). Can we
#       call create_testcameras() always and move this call here? Otherwise consider making 2
#       functions: non_streaming_testcameras_with_archive() and streaming_testcameras_with_archive()
def testcameras_with_archive(
        nx_server: Mediaserver,
        video_file: str,
        offset_from_now_sec: float,
        camera_count: int = 1,
        ) -> Sequence[Testcamera]:
    mediafile = SampleMediaFile(gui_prerequisite_store.fetch(video_file))
    mediafile_duration = mediafile.duration.total_seconds()
    if mediafile_duration > offset_from_now_sec:
        raise ValueError(f'offset_from_now_sec must be greater than {mediafile_duration}')
    tz_aware_dt = datetime.now(timezone.utc) - timedelta(seconds=offset_from_now_sec)
    return nx_server.add_cameras_with_archive(
        sample_media_file=mediafile,
        start_times=[tz_aware_dt],
        count=camera_count,
        )


def testcameras_with_just_recorded_archive(
        nx_server: Mediaserver,
        video_file: str,
        camera_count: int = 1,
        ) -> Sequence[Testcamera]:
    mediafile = SampleMediaFile(gui_prerequisite_store.fetch(video_file))
    tz_aware_dt = datetime.now(timezone.utc) - mediafile.duration
    return nx_server.add_cameras_with_archive(
        sample_media_file=mediafile,
        start_times=[tz_aware_dt],
        count=camera_count,
        )


@contextmanager
def different_playing_testcameras(
        machine_pool,
        os_access: OsAccess,
        primary_files: Sequence[str],
        ) -> AbstractContextManager[TestCameraApp]:
    benchmark = machine_pool.install_benchmark(os_access)
    camera_configs = []
    idx = 1
    for primary_file in primary_files:
        name = f'TestCamera-{idx:02d}'
        camera_configs.append(
            TestCameraConfig(_copy_file(benchmark.os_access, primary_file), name=name))
        idx += 1
    testcamera_app = benchmark.different_testcameras(camera_configs)
    with testcamera_app.running():
        yield testcamera_app


@contextmanager
def similar_playing_testcameras(
        machine_pool,
        os_access,
        primary_prerequisite,
        count,
        ) -> AbstractContextManager[TestCameraApp]:
    benchmark = machine_pool.install_benchmark(os_access)
    primary_on_remote = _copy_file(benchmark.os_access, primary_prerequisite)
    names = [f'TestCamera-{idx:02d}' for idx in range(1, count + 1)]
    camera_configs = [
        TestCameraConfig(hi_res_sample=primary_on_remote, name=name) for name in names]
    # Can not call benchmark.similar_testcameras() because we need cameras with different names
    testcamera_app = benchmark.different_testcameras(camera_configs=camera_configs)
    with testcamera_app.running():
        yield testcamera_app


@contextmanager
def similar_playing_testcameras_hi_low(
        primary_prerequisite,
        secondary_prerequisite,
        count,
        benchmark_server: VmsBenchmarkInstallation,
        ) -> AbstractContextManager[TestCameraApp]:
    hi_res_sample = _copy_file(benchmark_server.os_access, primary_prerequisite)
    if secondary_prerequisite is not None:
        low_res_sample = _copy_file(benchmark_server.os_access, secondary_prerequisite)
    else:
        low_res_sample = None
    camera_config = TestCameraConfig(
        hi_res_sample=hi_res_sample, low_res_sample=low_res_sample, name='TestCamera')
    testcamera_app = benchmark_server.similar_testcameras(camera_config, count)
    with testcamera_app.running():
        yield testcamera_app


@contextmanager
def playing_testcamera(
        machine_pool,
        os_access: OsAccess,
        primary_prerequisite: str,
        secondary_prerequisite: Optional[str] = None,
        ) -> AbstractContextManager[TestCameraApp]:
    benchmark = machine_pool.install_benchmark(os_access)
    primary_on_remote = _copy_file(benchmark.os_access, primary_prerequisite)
    if secondary_prerequisite is not None:
        secondary_on_remote = _copy_file(benchmark.os_access, secondary_prerequisite)
    else:
        secondary_on_remote = None
    camera_name = 'TestCamera-01'
    testcamera_app = benchmark.single_testcamera(
        camera_config=TestCameraConfig(
            hi_res_sample=primary_on_remote,
            low_res_sample=secondary_on_remote,
            name=camera_name,
            ),
        )
    with testcamera_app.running():
        yield testcamera_app


def _copy_file(os_access, file_name):
    local_media_file = gui_prerequisite_store.fetch(file_name)
    vm_media_file = os_access.path('/home/work/') / file_name
    vm_media_file.parent.mkdir(parents=True, exist_ok=True)
    copy_file(local_media_file, vm_media_file)
    return vm_media_file


_logger = logging.getLogger(__name__)
