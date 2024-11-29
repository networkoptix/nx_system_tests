# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.virtual_camera.common import watch_video


def _test_upload_different_containers(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    virtual_camera_id = api.add_virtual_camera('Virtual camera')
    mkv_file_path = default_prerequisite_store.fetch('test-cam/virtual/mkv.mkv')
    avi_file_path = default_prerequisite_store.fetch('test-cam/virtual/avi.avi')
    mp4_file_path = default_prerequisite_store.fetch('test-cam/virtual/mp4.mp4')
    mov_file_path = default_prerequisite_store.fetch('test-cam/virtual/mov.mov')
    with api.virtual_camera_locked(virtual_camera_id) as lock_token:
        mkv_start_time_sec = extract_start_timestamp(mkv_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            mkv_file_path,
            lock_token=lock_token,
            start_time_ms=mkv_start_time_sec)
        [[mkv_period]] = api.list_recorded_periods([virtual_camera_id], empty_ok=False)
        mkv_video_properties = watch_video(api, virtual_camera_id, mkv_period)
        mkv_video_duration = mkv_video_properties['duration_sec']
        assert abs(mkv_video_duration - mkv_period.duration_sec) <= 1
        avi_start_time_sec = extract_start_timestamp(avi_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            avi_file_path,
            lock_token=lock_token,
            start_time_ms=avi_start_time_sec)
        [[avi_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[mkv_period]], empty_ok=False)
        avi_video_properties = watch_video(api, virtual_camera_id, avi_period)
        avi_video_duration = avi_video_properties['duration_sec']
        assert abs(avi_video_duration - avi_period.duration_sec) <= 1
        mp4_start_time_sec = extract_start_timestamp(mp4_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            mp4_file_path,
            lock_token=lock_token,
            start_time_ms=mp4_start_time_sec)
        [[mp4_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[mkv_period, avi_period]], empty_ok=False)
        mp4_video_properties = watch_video(api, virtual_camera_id, mp4_period)
        mp4_video_duration = mp4_video_properties['duration_sec']
        assert abs(mp4_video_duration - mp4_period.duration_sec) <= 1
        mov_start_time_sec = extract_start_timestamp(mov_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            mov_file_path,
            lock_token=lock_token,
            start_time_ms=mov_start_time_sec)
        [[mov_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[mkv_period, avi_period, mp4_period]],
            empty_ok=False)
        mov_video_properties = watch_video(api, virtual_camera_id, mov_period)
        mov_video_duration = mov_video_properties['duration_sec']
        assert abs(mov_video_duration - mov_period.duration_sec) <= 1
