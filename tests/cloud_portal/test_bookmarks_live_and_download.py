# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from _internal.service_registry import default_prerequisite_store
from browser.chrome import ChromeConfiguration
from browser.chrome import RemoteChromeDownloadDirectory
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import H264RtspCameraServer
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.ffprobe import video_is_valid
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from os_access import RemotePath
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._bookmarks import BookmarkDialog
from tests.cloud_portal._bookmarks import BookmarkDownloadModal
from tests.cloud_portal._bookmarks import BookmarksComponent
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_toolbar import SystemToolBar
from vm.networks import setup_flat_network


class test_bookmarks_live_and_download(VMSTest, CloudTest):
    """Test bookmarks live download.

    Selection-Tag: 128468
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128468
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
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        browser_downloads_path = browser_stand.vm().os_access.tmp() / 'exported_video'
        browser_downloads_path.mkdir()
        chrome_download_directory = RemoteChromeDownloadDirectory(browser_downloads_path)
        chrome_configuration = ChromeConfiguration()
        chrome_download_directory.apply_to(chrome_configuration)
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.set_license_server(license_server.url())
        grant_license(mediaserver, license_server)
        media_sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample_gop_15.264'))
        camera_server = H264RtspCameraServer(
            source_video_file=media_sample.path,
            fps=media_sample.fps,
            )
        [camera] = add_cameras(mediaserver, camera_server)
        start = int(mediaserver.api.get_datetime().timestamp() * 1000)
        record_from_cameras(
            mediaserver.api,
            [camera],
            camera_server,
            duration_sec=10,
            )
        bookmark_name = 'test_bookmark_one'
        mediaserver.api.add_bookmark(
            camera.id,
            bookmark_name,
            start_time_ms=start + 2,
            duration_ms=3000,
            description='bookmark_one_initial',
            )
        mediaserver.api.setup_cloud_system(cloud_account)
        browser = exit_stack.enter_context(browser_stand.browser(chrome_configuration))
        link = f"https://{cloud_host}/systems/{mediaserver.api.get_cloud_system_id()}"
        browser.open(link)
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=20)
        SystemToolBar(browser).open_bookmarks()
        BookmarksComponent(browser).open_bookmark(bookmark_name)
        bookmark_dialog = BookmarkDialog(browser)
        bookmark_dialog.wait_for_playing_video()
        bookmark_dialog.get_download_button().invoke()
        bookmark_download = BookmarkDownloadModal(browser)
        assert bookmark_download.get_title() == f"Download {bookmark_name}"
        expected_text = "The length of this bookmark will be slightly increased to maintain video quality"
        assert bookmark_download.get_body_text() == expected_text
        bookmark_download.get_download_button().invoke()
        exported_file = _get_exported_video_file(browser_downloads_path)
        local_copy = get_run_dir() / exported_file.name
        local_copy.write_bytes(exported_file.read_bytes())
        assert video_is_valid(local_copy)


def _get_exported_video_file(path: RemotePath) -> RemotePath:
    timeout = 20
    started_at = time.monotonic()
    while True:
        mp4_files = list(path.glob('*.mp4'))
        if mp4_files:
            [exported_file] = mp4_files
            return exported_file
        if time.monotonic() - started_at > timeout:
            raise TimeoutError(f"{path} does not contain .mp4 files after {timeout} seconds")
        time.sleep(1)


if __name__ == '__main__':
    exit(test_bookmarks_live_and_download().main())
