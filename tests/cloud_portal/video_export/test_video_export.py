# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timezone
from typing import Sequence

from _internal.service_registry import default_prerequisite_store
from browser.chrome import ChromeConfiguration
from browser.chrome import RemoteChromeDownloadDirectory
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.ffprobe import video_is_valid
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import RemotePath
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_toolbar import SystemToolBar
from tests.cloud_portal._toast_notification import CookieBanner
from tests.cloud_portal.video_export._archive_navigation import Timeline
from tests.cloud_portal.video_export._archive_navigation import TimelineSelectionActionPanel
from tests.cloud_portal.video_export._view_sidebar import ViewSidebar


class test_video_export(VMSTest, CloudTest):
    """Test video export.

    Selection-Tag: 120737
    Selection-Tag: 128470
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120737
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128470
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser_downloads_path = browser_stand.vm().os_access.tmp() / 'exported_video'
        browser_downloads_path.mkdir()
        chrome_download_directory = RemoteChromeDownloadDirectory(browser_downloads_path)
        chrome_configuration = ChromeConfiguration()
        chrome_download_directory.apply_to(chrome_configuration)
        browser = exit_stack.enter_context(browser_stand.browser(chrome_configuration))
        mediaserver = mediaserver_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_owner)
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
        link = f"https://{cloud_host}/systems/{mediaserver.api.get_cloud_system_id()}/"
        browser.open(link)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.wait_for_system_name_field(timeout=90)
        banner = CookieBanner(browser)
        if banner.is_visible():
            banner.close()
        SystemToolBar(browser).open_view()
        server_name = mediaserver.api.get_server_info().server_name
        server_camera_list = ViewSidebar(browser).get_server_camera_list(server_name)
        camera_h265_thumbnail = server_camera_list.get_camera_thumbnail(camera_h265.name)
        camera_h264_thumbnail = server_camera_list.get_camera_thumbnail(camera_h264.name)
        camera_mjpeg_thumbnail = server_camera_list.get_camera_thumbnail(camera_mjpeg.name)
        camera_h265_thumbnail.select()
        Timeline(browser).select_relative_part(0.25, 0.75)
        TimelineSelectionActionPanel(browser).start_export()
        camera_h264_thumbnail.select()
        Timeline(browser).select_relative_part(0.2, 0.8)
        TimelineSelectionActionPanel(browser).start_export()
        camera_mjpeg_thumbnail.select()
        Timeline(browser).select_relative_part(0.4, 0.9)
        TimelineSelectionActionPanel(browser).start_export()
        exported_h265_video = _make_local_copy_of_exported_footage(
            camera_h265.name, browser_downloads_path)
        assert video_is_valid(exported_h265_video)
        exported_h264_mkv = _make_local_copy_of_exported_footage(
            camera_h264.name, browser_downloads_path)
        assert video_is_valid(exported_h264_mkv)
        exported_mjpeg_mkv = _make_local_copy_of_exported_footage(
            camera_mjpeg.name, browser_downloads_path)
        assert video_is_valid(exported_mjpeg_mkv)


def _make_local_copy_of_exported_footage(camera_name: str, remote_export_dir: RemotePath):
    try:
        [exported_file] = _get_exported_video_for_camera(remote_export_dir, camera_name)
    except TimeoutError as e:
        if 'does not contain .mkv files for camera' in str(e):
            raise RuntimeError(
                f"Cannot find .mkv files for camera {camera_name} meeting the required "
                f"format CameraName_date.mkv. It can be related to a known bug."
                f"See: https://networkoptix.atlassian.net/browse/CLOUD-15156")
        else:
            raise
    local_copy = get_run_dir() / exported_file.name
    local_copy.write_bytes(exported_file.read_bytes())
    return local_copy


def _get_exported_video_for_camera(path: RemotePath, camera_name: str) -> Sequence[RemotePath]:
    timeout = 20
    started_at = time.monotonic()
    while True:
        mkv_files = list(path.glob('*.mkv'))
        if mkv_files:
            camera_files = [file for file in mkv_files if camera_name in file.stem]
            if camera_files:
                return camera_files
        if time.monotonic() - started_at > timeout:
            raise TimeoutError(
                f"{path} does not contain .mkv files for camera {camera_name} "
                f"after {timeout} seconds")
        time.sleep(1)


if __name__ == '__main__':
    exit(test_video_export().main())
