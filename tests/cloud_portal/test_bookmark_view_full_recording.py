# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import timedelta
from ipaddress import IPv4Network

from _internal.service_registry import default_prerequisite_store
from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._bookmarks import BookmarkDialog
from tests.cloud_portal._bookmarks import BookmarksComponent
from tests.cloud_portal._bookmarks import Calendar
from tests.cloud_portal._camera_playback import CameraPlayback
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal.video_export._archive_navigation import ColoredChunkSequence
from tests.cloud_portal.video_export._archive_navigation import Timeline
from vm.networks import setup_flat_network

_logger = logging.getLogger(__name__)


class test_bookmark_view_full_recording(VMSTest, CloudTest):
    """Test bookmark view full recording.

    Selection-Tag: 128467
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128467
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['bookmarks', 'newHeader'])
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = mediaserver_stand.mediaserver()
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        cloud_account = cloud_account_factory.create_account()
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [mediaserver_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_account)
        sample_media_file = SampleMediaFile(
            default_prerequisite_store.fetch('test-cam/high.ts'))
        start = mediaserver.api.get_datetime() - timedelta(minutes=2)
        [camera] = mediaserver.add_cameras_with_archive(
            sample_media_file=sample_media_file,
            start_times=[start],
            )
        mediaserver.api.rebuild_main_archive()
        half_duration_ms = int(sample_media_file.duration.total_seconds() * 1000 // 2)
        bookmark_name = 'test_bookmark_one'
        mediaserver.api.add_bookmark(
            camera.id,
            bookmark_name,
            start_time_ms=int(start.timestamp() * 1000) + half_duration_ms,
            duration_ms=half_duration_ms // 2,
            description='bookmark_one_initial',
            )
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        # As it is not the main functionality of the test to check the system toolbar options,
        # the decision to proceed by link was made. It decreases probability of the test falling down
        # due to FT Cloud Portal being too slow if multiple tests are run simultaneously.
        link = f"https://{cloud_host}/systems/{mediaserver.api.get_cloud_system_id()}/bookmarks/"
        browser.open(link)
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        bookmark_component = BookmarksComponent(browser)
        # Falls down here if multiple tests are run in parallel on FT Cloud.
        # Not related to test itself but general FT Cloud problem.
        Calendar(browser).wait_until_exists()
        bookmark_component.open_bookmark(bookmark_name)
        bookmark_dialog = BookmarkDialog(browser)
        bookmark_dialog.get_view_recording_button().invoke()
        [_, second_tab] = browser.get_tabs()
        second_tab.switch_to()
        assert 'view' in browser.get_current_url()
        camera_playback = CameraPlayback(browser)
        assert camera.name == camera_playback.get_playing_camera_name()
        assert _is_playing_from_the_middle(browser)
        camera_playback.wait_for_playing_video()


def _is_playing_from_the_middle(browser: Browser) -> bool:
    timeline = Timeline(browser)
    timeline.get_pause_button().invoke()
    sequence = _get_archive_chunk_sequence(timeline)
    sequence_length = sequence.get_length()
    if sequence_length != 2:
        raise RuntimeError(f"Wrong quantity of chunks. Expected 2, got {sequence_length}")
    first_chunk = sequence.get_first()
    second_chunk = sequence.get_last()
    current_position_is_thin = abs(second_chunk.start - first_chunk.end) <= 5
    chunks_are_equal = abs(first_chunk.get_length() - second_chunk.get_length()) <= 5
    timeline.get_play_button().invoke()
    return current_position_is_thin and chunks_are_equal


def _get_archive_chunk_sequence(timeline: Timeline) -> ColoredChunkSequence:
    timeout = 5
    started_at = time.monotonic()
    while True:
        chunk_sequence = timeline.get_archive_chunk_sequence()
        if chunk_sequence.get_length() > 0:
            return chunk_sequence
        else:
            _logger.info("No archive chunk found yet")
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(f"No green chunk within {timeout} seconds timeout")
        time.sleep(1)


if __name__ == '__main__':
    exit(test_bookmark_view_full_recording().main())
