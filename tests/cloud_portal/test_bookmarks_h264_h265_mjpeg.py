# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from datetime import timezone
from ipaddress import IPv4Network

from _internal.service_registry import default_prerequisite_store
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._bookmarks import BookmarkDialog
from tests.cloud_portal._bookmarks import BookmarksComponent
from tests.cloud_portal._bookmarks import Calendar
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import LoginComponent
from vm.networks import setup_flat_network

_logger = logging.getLogger(__name__)


class test_bookmarks_h264_h265_mjpeg(VMSTest, CloudTest):
    """Test bookmark previews for H264, H265 and MJPEG.

    Selection-Tag: 128466
    Selection-Tag: cloud_portal
    Selection-Tag: xfail
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128466
    xfail reason: https://networkoptix.atlassian.net/browse/CLOUD-13984
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['bookmarks'])
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        cloud_account = cloud_account_factory.create_account()
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.set_license_server(license_server.url())
        grant_license(mediaserver, license_server)
        mediaserver.api.setup_cloud_system(cloud_account)
        start_time = datetime(2024, 4, 9, tzinfo=timezone.utc)
        sample_h265 = SampleMediaFile(
            default_prerequisite_store.fetch('test-cam/low_265.ts'))
        [camera_h265] = mediaserver.add_cameras_with_archive(
            sample_media_file=sample_h265,
            start_times=[start_time],
            offset=0,
            )
        sample_h264 = SampleMediaFile(
            default_prerequisite_store.fetch('test-cam/low_264.mkv'))
        [camera_h264] = mediaserver.add_cameras_with_archive(
            sample_media_file=sample_h264,
            start_times=[start_time],
            offset=1,
            )
        sample_mjpeg = SampleMediaFile(
            default_prerequisite_store.fetch('test-cam/mjpeg.mp4'))
        [camera_mjpeg] = mediaserver.add_cameras_with_archive(
            sample_media_file=sample_mjpeg,
            start_times=[start_time],
            offset=2,
            )
        mediaserver.api.rebuild_main_archive()
        bookmark_name_h264 = 'test_bookmark_h264'
        all_durations = [sample_h264.duration, sample_h265.duration, sample_mjpeg.duration]
        min_sample_duration_ms = int(min(all_durations).total_seconds() * 1000)
        start_time_ms = int(start_time.timestamp() * 1000)
        mediaserver.api.add_bookmark(
            camera_h264.id,
            bookmark_name_h264,
            start_time_ms=start_time_ms + min_sample_duration_ms // 2,
            duration_ms=min_sample_duration_ms // 3,
            description='bookmark_h264_initial',
            )
        bookmark_name_h265 = 'test_bookmark_h265'
        mediaserver.api.add_bookmark(
            camera_h265.id,
            bookmark_name_h265,
            start_time_ms=start_time_ms + min_sample_duration_ms // 2,
            duration_ms=min_sample_duration_ms // 3,
            description='bookmark_h265_initial',
            )
        bookmark_name_mjpeg = 'test_bookmark_mjpeg'
        mediaserver.api.add_bookmark(
            camera_mjpeg.id,
            bookmark_name_mjpeg,
            start_time_ms=start_time_ms + min_sample_duration_ms // 2,
            duration_ms=min_sample_duration_ms // 3,
            description='bookmark_mjpeg_initial',
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
        bookmark_component.open_bookmark(bookmark_name_h264)
        bookmark_dialog = BookmarkDialog(browser)
        # Placeholder on unsupported format appears instead of playing video.
        # See: https://networkoptix.atlassian.net/browse/CLOUD-13984
        bookmark_dialog.wait_for_playing_video()
        bookmark_dialog.close()
        bookmark_component.open_bookmark(bookmark_name_h265)
        # Placeholder on unsupported format appears instead of playing video.
        # See: https://networkoptix.atlassian.net/browse/CLOUD-13984
        bookmark_dialog.wait_for_playing_video()
        bookmark_dialog.close()
        bookmark_component.open_bookmark(bookmark_name_mjpeg)
        assert element_is_present(bookmark_dialog.get_video_format_error)


if __name__ == '__main__':
    exit(test_bookmarks_h264_h265_mjpeg().main())
