# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises
from tests.single_server.permissions.common import get_api_for_actor


def _test_cannot_watch_an_archive(distrib_url, one_vm_type, api_version, actor, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    [dummy_camera] = mediaserver.add_cameras_with_archive(
        sample_media_file=SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv')),
        start_times=[datetime(2019, 1, 11, tzinfo=timezone.utc)],
        )
    mediaserver_api_for_actor = get_api_for_actor(mediaserver.api, actor)
    with assert_raises(Forbidden):
        mediaserver_api_for_actor.list_recorded_periods([dummy_camera.id])
