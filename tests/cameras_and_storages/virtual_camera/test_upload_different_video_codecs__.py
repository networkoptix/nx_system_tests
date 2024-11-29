# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.virtual_camera.common import watch_video


def _test_upload_different_video_codecs(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    h264_file_path = default_prerequisite_store.fetch('test-cam/virtual/h264_aac.mp4')
    h265_file_path = default_prerequisite_store.fetch('test-cam/virtual/h265_short.mkv')
    mjpeg_file_path = default_prerequisite_store.fetch('test-cam/virtual/mjpeg.mkv')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    virtual_camera_id = api.add_virtual_camera('Virtual camera')
    with api.virtual_camera_locked(virtual_camera_id) as lock_token:
        h264_start_time_sec = extract_start_timestamp(h264_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            h264_file_path,
            lock_token=lock_token,
            start_time_ms=h264_start_time_sec)
        [[h264_period]] = api.list_recorded_periods([virtual_camera_id], empty_ok=False)
        h264_video_properties = watch_video(api, virtual_camera_id, h264_period)
        h264_video_duration = h264_video_properties['duration_sec']
        assert abs(h264_video_duration - h264_period.duration_sec) <= 1
        assert _get_video_codec(h264_video_properties) == 'h264'
        h265_start_time_sec = extract_start_timestamp(h265_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            h265_file_path,
            lock_token=lock_token,
            start_time_ms=h265_start_time_sec)
        [[h265_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[h264_period]], empty_ok=False)
        h265_video_properties = watch_video(api, virtual_camera_id, h265_period)
        h265_video_duration = h265_video_properties['duration_sec']
        assert abs(h265_video_duration - h265_period.duration_sec) <= 1
        assert _get_video_codec(h265_video_properties) == 'hevc'
        mjpeg_start_time_sec = extract_start_timestamp(mjpeg_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            mjpeg_file_path,
            lock_token=lock_token,
            start_time_ms=mjpeg_start_time_sec)
        [[mjpeg_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[h264_period, h265_period]], empty_ok=False)
        mjpeg_video_properties = watch_video(api, virtual_camera_id, mjpeg_period)
        mjpeg_video_duration = mjpeg_video_properties['duration_sec']
        assert abs(mjpeg_video_duration - mjpeg_period.duration_sec) <= 1
        assert _get_video_codec(mjpeg_video_properties) == 'mjpeg'


def _get_video_codec(video_properties):
    [stream] = [s for s in video_properties['streams'] if s['codec_type'] == 'video']
    return stream['codec_name']
