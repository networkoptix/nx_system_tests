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

_logger = logging.getLogger(__name__)


def _test_merged_and_separated_archive(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()

    [camera] = one.api.add_test_cameras(offset=0, count=1)

    sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    _logger.debug('Sample duration: %s', sample.duration)

    start_times_one = []
    start_times_one.append(datetime(2017, 1, 27, tzinfo=timezone.utc))
    start_times_one.append(start_times_one[-1] + sample.duration - timedelta(seconds=10))  # overlapping with previous
    start_times_one.append(start_times_one[-1] + sample.duration + timedelta(minutes=1))   # separate from previous
    start_times_two = []
    start_times_two.append(start_times_one[-1] + sample.duration + timedelta(minutes=1))   # separate from previous
    start_times_two.append(start_times_two[-1] + sample.duration)                          # adjacent to previous
    _logger.debug("Start times for server one: %r", start_times_one)
    _logger.debug("Start times for server two: %r", start_times_two)
    expected_periods_one = [
        TimePeriod.from_datetime(
            start_times_one[0],
            sample.duration * 2 - timedelta(seconds=10)),  # overlapped must be joined together
        TimePeriod.from_datetime(
            start_times_one[2],
            sample.duration),
        ]
    expected_periods_two = [
        TimePeriod.from_datetime(start_times_two[0], sample.duration * 2),  # adjacent must be joined together
        ]
    all_expected_periods = expected_periods_one + expected_periods_two
    _logger.debug("Expected periods for server one: %r", expected_periods_one)
    _logger.debug("Expected periods for server two: %r", expected_periods_two)

    for st in start_times_one:
        one.default_archive().camera_archive(camera.physical_id).save_media_sample(st, sample)
    for st in start_times_two:
        two.default_archive().camera_archive(camera.physical_id).save_media_sample(st, sample)
    one.api.rebuild_main_archive()
    two.api.rebuild_main_archive()
    assert [all_expected_periods] == one.api.list_recorded_periods([camera.id])
    assert [all_expected_periods] == two.api.list_recorded_periods([camera.id])
    one.api.detach_from_system()
    one.api.setup_local_system()
    assert [expected_periods_one] == one.api.list_recorded_periods([camera.id])
    assert [expected_periods_two] == two.api.list_recorded_periods([camera.id])
