# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_saved_media_should_appear_after_archive_is_rebuilt(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    start_time = datetime(2017, 3, 27, tzinfo=timezone.utc)
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    [camera] = server.add_cameras_with_archive(
        sample_media_file=sample_media_file,
        start_times=[start_time],
        )
    server.api.rebuild_main_archive()
    [[period]] = server.api.list_recorded_periods([camera.id])
    assert period.start == start_time
    assert period.duration_sec == sample_media_file.duration.total_seconds()
