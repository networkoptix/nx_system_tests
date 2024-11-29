# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.virtual_camera.common import watch_video
from tests.infra import Skip


def _test_upload_different_audio_codecs(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    virtual_camera_id = api.add_virtual_camera('Virtual camera')
    if one_mediaserver.mediaserver().branch() in ['vms_5.0_patch', 'vms_5.0']:
        raise Skip("Temporarily skipped; Under investigation")
    aac_file_path = default_prerequisite_store.fetch('test-cam/virtual/h264_aac.mp4')
    g711_file_path = default_prerequisite_store.fetch('test-cam/virtual/g711.mkv')
    g726_file_path = default_prerequisite_store.fetch('test-cam/virtual/g726.mkv')
    with api.virtual_camera_locked(virtual_camera_id) as lock_token:
        aac_start_time_sec = extract_start_timestamp(aac_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            aac_file_path,
            lock_token=lock_token,
            start_time_ms=aac_start_time_sec)
        [[aac_period]] = api.list_recorded_periods([virtual_camera_id], empty_ok=False)
        aac_video_properties = watch_video(api, virtual_camera_id, aac_period)
        aac_video_duration = aac_video_properties['duration_sec']
        assert abs(aac_video_duration - aac_period.duration_sec) <= 1
        assert _get_audio_codec(aac_video_properties) == 'aac'
        g711_start_time_sec = extract_start_timestamp(g711_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            g711_file_path,
            lock_token=lock_token,
            start_time_ms=g711_start_time_sec)
        [[g711_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[aac_period]], empty_ok=False)
        g711_video_properties = watch_video(api, virtual_camera_id, g711_period)
        g711_video_duration = g711_video_properties['duration_sec']
        assert abs(g711_video_duration - g711_period.duration_sec) <= 1
        assert _get_audio_codec(g711_video_properties) == 'mp3'
        g726_start_time_sec = extract_start_timestamp(g726_file_path)
        api.upload_to_virtual_camera(
            virtual_camera_id,
            g726_file_path,
            lock_token=lock_token,
            start_time_ms=g726_start_time_sec)
        [[g726_period]] = api.list_recorded_periods(
            [virtual_camera_id], skip_periods=[[aac_period, g711_period]], empty_ok=False)
        g726_video_properties = watch_video(api, virtual_camera_id, g726_period)
        g726_video_duration = g726_video_properties['duration_sec']
        assert abs(g726_video_duration - g726_period.duration_sec) <= 1
        assert _get_audio_codec(g726_video_properties) == 'mp3'


def _get_audio_codec(video_properties):
    [stream] = [s for s in video_properties['streams'] if s['codec_type'] == 'audio']
    return stream['codec_name']
