# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.media_stream.common import assert_server_stream


def _test_get_streams(distrib_url, stream_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'outer', 'type': 'ubuntu22'},
            {'alias': 'inner', 'type': 'ubuntu22'},
            {'alias': 'router', 'type': 'ubuntu22'},
            ],
        'mergers': [
            {'local': 'inner', 'remote': 'outer', 'take_remote_settings': False},
            ],
        'networks': {
            '10.254.0.0/28': {
                'outer': None,
                'router': {
                    '10.254.0.16/28': {
                        'inner': None,
                        },
                    },
                },
            },
        }))
    [system, _, _] = network_and_system
    artifacts_dir = get_run_dir()
    [camera] = system['inner'].api.add_test_cameras(offset=0, count=1)
    start_time_1 = datetime(2017, 1, 27, tzinfo=timezone.utc)
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    system['outer'].default_archive().camera_archive(camera.physical_id).save_media_sample(
        start_time_1, sample_media_file)
    system['outer'].api.rebuild_main_archive()
    start_time_2 = datetime(2017, 2, 27, tzinfo=timezone.utc)
    system['inner'].default_archive().camera_archive(camera.physical_id).save_media_sample(
        start_time_2, sample_media_file)
    system['inner'].api.rebuild_main_archive()
    assert_server_stream(
        system['inner'], camera, sample_media_file, stream_type, artifacts_dir, start_time_1)
    assert_server_stream(
        system['outer'], camera, sample_media_file, stream_type, artifacts_dir, start_time_1)
    assert_server_stream(
        system['inner'], camera, sample_media_file, stream_type, artifacts_dir, start_time_2)
    assert_server_stream(
        system['outer'], camera, sample_media_file, stream_type, artifacts_dir, start_time_2)
