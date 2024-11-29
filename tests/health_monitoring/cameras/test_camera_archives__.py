# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from collections import namedtuple
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import ApproxAbs
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import add_local_storage
from tests.health_monitoring.common import add_test_cameras

Camera = namedtuple('Camera', 'id physical_id')
FakeArchive = namedtuple('FakeArchive', 'server_time_sec archive_relative_time_sec')


def _create_cameras(mediaserver, cameras_count):
    camera_ids = add_test_cameras(mediaserver, cameras_count=cameras_count)
    return [
        Camera(camera.id, camera.physical_id)
        for camera in mediaserver.api.list_cameras()
        if camera.id in camera_ids]


def _create_cameras_with_fake_archives(mediaserver, storage):
    camera_data = _create_cameras(mediaserver, 3)
    server_time = mediaserver.api.get_datetime()
    first_relative_time = timedelta(seconds=180)
    second_relative_time = timedelta(seconds=480)
    chunks_args = {
        'duration_sec': 32,
        'bitrate_bps': 1 * 10**6,
        'chunk_duration_sec': 1,
        }
    storage.camera_archive(camera_data[0].physical_id).high().add_fake_record(
        start_time=server_time - first_relative_time,
        **chunks_args,
        )
    storage.camera_archive(camera_data[0].physical_id).low().add_fake_record(
        start_time=server_time - second_relative_time,
        **chunks_args,
        )
    storage.camera_archive(camera_data[1].physical_id).high().add_fake_record(
        start_time=server_time - first_relative_time,
        **chunks_args,
        )
    storage.camera_archive(camera_data[2].physical_id).low().add_fake_record(
        start_time=server_time - first_relative_time,
        **chunks_args,
        )

    return {
        camera_data[0].id: FakeArchive(
            server_time.timestamp(),
            second_relative_time.total_seconds()),
        camera_data[1].id: FakeArchive(
            server_time.timestamp(),
            first_relative_time.total_seconds()),
        camera_data[2].id: FakeArchive(
            server_time.timestamp(),
            first_relative_time.total_seconds()),
        }


def _test_camera_archives(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    camera_archives_main = _create_cameras_with_fake_archives(mediaserver, mediaserver.default_archive())
    local_storage_path = add_local_storage(mediaserver, storage_size_bytes=30 * 1024**3)
    [local_storage] = mediaserver.api.list_storages(within_path=str(local_storage_path))
    mediaserver.api.allocate_storage_for_backup(local_storage.id)
    backup_archive = mediaserver.archive(local_storage.path)
    camera_archives_backup = _create_cameras_with_fake_archives(mediaserver, backup_archive)
    camera_data = _create_cameras(mediaserver, 5)
    server_time = mediaserver.api.get_datetime()
    default_archive = mediaserver.default_archive()
    archive_relative_times = [
        timedelta(minutes=30),
        timedelta(hours=7),
        timedelta(days=4),
        timedelta(days=90),
        timedelta(days=365 * 3),
        ]
    archives_with_different_start_time = {}
    chunk_duration_sec = 1
    for camera, arch_rel_time in zip(camera_data, archive_relative_times):
        default_archive.camera_archive(camera.physical_id).high().add_fake_record(
            start_time=server_time - arch_rel_time,
            duration_sec=4 * chunk_duration_sec,
            bitrate_bps=1 * 10**6,
            chunk_duration_sec=chunk_duration_sec,
            )
        archives_with_different_start_time[camera.id] = FakeArchive(
            server_time.timestamp(),
            arch_rel_time.total_seconds())
    archive_data = {
        **archives_with_different_start_time,
        **camera_archives_main,
        **camera_archives_backup}

    expected_lengths = {}

    for camera_id, fake_archive in archive_data.items():
        expected_lengths[camera_id] = ApproxAbs(
            fake_archive.archive_relative_time_sec,
            1)

    mediaserver.api.restart()

    current = mediaserver.api.get_datetime().timestamp()
    # Work around issue, when metrics have no archiveLengthS attribute.
    # Probably, metrics need some time to initialize, and it is OK.
    camera_metrics = _wait_for_camera_metrics(mediaserver.api)

    actual_lengths = {}
    for camera_id in camera_metrics:
        time_bias = current - archive_data[camera_id].server_time_sec
        length = camera_metrics[camera_id]['archive_length_sec']
        actual_lengths[camera_id] = length - time_bias

    assert expected_lengths == actual_lengths


def _wait_for_camera_metrics(api):
    started_at = time.monotonic()
    while True:
        camera_metrics = api.get_metrics('cameras')
        if all(metrics.get('archive_length_sec') is not None for metrics in camera_metrics.values()):
            return camera_metrics
        if time.monotonic() - started_at > 2:
            raise TimeoutError("Timed out waiting for camera metrics")
        time.sleep(0.2)
