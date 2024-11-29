# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from doubles.licensing.local_license_server import LocalLicenseServer
from installation import Mediaserver
from mediaserver_scenarios.license_scenarios import grant_license
from vm.hypervisor import Vm


def configure_mediaserver(
        license_server: LocalLicenseServer,
        mediaserver: Mediaserver,
        ):
    mediaserver.update_conf({'mediaFileDuration': 1})  # To make tests faster
    mediaserver.start()
    with license_server.serving():
        mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
        grant_license(mediaserver, license_server)
    [default] = mediaserver.api.list_storages()
    mediaserver.api.disable_storage(default.id)


def add_two_archives(mediaserver: Mediaserver, vm_control: Vm):
    os = mediaserver.os_access
    api = mediaserver.api
    disk_size_mb = 20 * 1024
    vm_control.add_disk('sata', disk_size_mb)
    first_path = os.mount_disk('F')
    vm_control.add_disk('sata', disk_size_mb)
    second_path = os.mount_disk('S')
    [_, first_storage] = api.set_up_new_storage(first_path)
    [_, second_storage] = api.set_up_new_storage(second_path)
    first_archive = mediaserver.archive(first_storage.path)
    second_archive = mediaserver.archive(second_storage.path)
    return first_archive, second_archive


def _prepare_archive(
        api,
        first_archive,
        second_archive,
        camera,
        ):
    first_camera_archive = first_archive.camera_archive(camera.physical_id)
    second_camera_archive = second_archive.camera_archive(camera.physical_id)
    first_camera_archive.remove()
    second_camera_archive.remove()
    record_duration_sec = 45
    chunk_duration_sec = 10
    start_time_older = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    first_archive_period = first_camera_archive.high().add_fake_record(
        start_time=start_time_older,
        duration_sec=record_duration_sec,
        chunk_duration_sec=chunk_duration_sec,
        )
    start_time_newer = datetime(2020, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    second_archive_period = second_camera_archive.high().add_fake_record(
        start_time=start_time_newer,
        duration_sec=record_duration_sec,
        chunk_duration_sec=chunk_duration_sec,
        )
    api.rebuild_main_archive()
    [periods] = api.list_recorded_periods([camera.id])
    assert first_archive_period in periods
    assert second_archive_period in periods
    return first_archive_period, second_archive_period


def _fill_storage_with_other_data(os, storage):
    other_data_size = storage.free_space - storage.reserved_space - 1024**2
    other_data_path = os.path(storage.path) / 'other.bin'
    os.create_file(other_data_path, other_data_size)
