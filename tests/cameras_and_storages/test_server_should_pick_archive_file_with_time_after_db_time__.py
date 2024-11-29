# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_api import TimePeriod
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_server_should_pick_archive_file_with_time_after_db_time(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    [camera] = mediaserver.api.add_test_cameras(offset=0, count=1)
    camera_archive = mediaserver.default_archive().camera_archive(camera.physical_id)
    sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))

    start_times_1 = []
    start_times_1.append(datetime(2017, 1, 27, tzinfo=timezone.utc))
    start_times_1.append(start_times_1[-1] + sample.duration + timedelta(minutes=1))
    start_times_2 = []
    start_times_2.append(start_times_1[-1] + sample.duration + timedelta(minutes=1))
    start_times_2.append(start_times_2[-1] + sample.duration + timedelta(minutes=1))
    expected_periods_1 = [
        TimePeriod.from_datetime(start_times_1[0], sample.duration),
        TimePeriod.from_datetime(start_times_1[1], sample.duration),
        ]
    expected_periods_2 = [
        TimePeriod.from_datetime(start_times_2[0], sample.duration),
        TimePeriod.from_datetime(start_times_2[1], sample.duration),
        ]
    _logger.debug("Start times 1: %r", start_times_1)
    _logger.debug("Start times 2: %r", start_times_2)
    _logger.debug("Expected periods 1: %r", expected_periods_1)
    _logger.debug("Expected periods 2: %r", expected_periods_2)

    for st in start_times_1:
        camera_archive.save_media_sample(st, sample)
    mediaserver.api.rebuild_main_archive()
    assert [expected_periods_1] == mediaserver.api.list_recorded_periods([camera.id])

    # stop service and add more media files to archive:
    mediaserver.stop()
    for st in start_times_2:
        camera_archive.save_media_sample(st, sample)
    mediaserver.start()
    wait_for_truthy(
        lambda: 'beingRebuilt' not in mediaserver.api.list_storages()[0].status,
        description='Wait for archive to be rebuilt',
        )

    [recorded_periods] = mediaserver.api.list_recorded_periods(
        [camera.id], incomplete_ok=False, empty_ok=False)
    assert recorded_periods != expected_periods_1, 'Mediaserver did not pick up new media archive files'
    assert expected_periods_1 + expected_periods_2 == recorded_periods
