# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.media_stream.common import assert_server_stream


def _test_media_stream_should_be_loaded_correctly(distrib_url, one_vm_type, stream_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    artifacts_dir = get_run_dir()
    # prepare media archive
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    start_time = datetime(2017, 1, 27, tzinfo=timezone.utc)
    [camera] = mediaserver.add_cameras_with_archive(
        sample_media_file=sample_media_file,
        start_times=[start_time],
        )
    mediaserver.api.rebuild_main_archive()
    assert_server_stream(mediaserver, camera, sample_media_file, stream_type, artifacts_dir, start_time)
