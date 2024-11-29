# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from ipaddress import IPv4Network
from typing import Mapping
from typing import Union

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
from tests.cloud_portal._bookmarks import BookmarksComponent
from tests.cloud_portal._bookmarks import Calendar
from tests.cloud_portal._bookmarks import QuickSelect
from tests.cloud_portal._bookmarks import TimeRange
from tests.cloud_portal._bookmarks import _BookmarkInfo
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_toolbar import SystemToolBar
from tests.cloud_portal._translation import en_us
from vm.networks import setup_flat_network


class test_bookmark_filters(VMSTest, CloudTest):
    """Test bookmark filters.

    Selection-Tag: 128469
    Selection-Tag: 111619
    Selection-Tag: 111620
    Selection-Tag: 111621
    Selection-Tag: 131976
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128469
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/111619
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/111620
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/111621
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/131976
    """

    def _run(self, args, exit_stack):
        language = en_us
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
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.set_license_server(license_server.url())
        grant_license(mediaserver, license_server)
        mediaserver.api.setup_cloud_system(cloud_account)
        media_sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/high.ts'))
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        nine_days_ago = browser_stand.vm().os_access.get_datetime() - timedelta(days=9)
        # Avoid over-midnight ranges when doing isolated time selection testing
        bookmark_1_start = nine_days_ago.replace(hour=12)
        bookmark_2_start = bookmark_1_start + timedelta(days=5)
        sample_duration = media_sample.duration
        bookmark_duration = sample_duration * 2
        [camera_1] = mediaserver.add_cameras_with_archive(
            sample_media_file=media_sample,
            start_times=[
                (bookmark_1_start - sample_duration) + sample_duration * i
                for i in range((bookmark_duration // sample_duration) * 2)],
            count=1,
            offset=0,
            )
        [camera_2] = mediaserver.add_cameras_with_archive(
            sample_media_file=media_sample,
            start_times=[
                (bookmark_2_start - sample_duration) + sample_duration * i
                for i in range((bookmark_duration // sample_duration) * 2)],
            count=1,
            offset=1,
            )
        bookmark_duration_ms = int(bookmark_duration.total_seconds() * 1000)
        bookmark_1_name = "camera_1 test bookmark"
        mediaserver.api.add_bookmark(
            camera_id=camera_1.id,
            name=bookmark_1_name,
            start_time_ms=int(bookmark_1_start.timestamp() * 1000),
            duration_ms=bookmark_duration_ms,
            )
        bookmark_2_name = "camera_2 test bookmark"
        mediaserver.api.add_bookmark(
            camera_id=camera_2.id,
            name=bookmark_2_name,
            start_time_ms=int(bookmark_2_start.timestamp() * 1000),
            duration_ms=bookmark_duration_ms,
            )
        setup_flat_network(
            [mediaserver_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        system_id = mediaserver.api.get_cloud_system_id()
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f'https://{cloud_host}/{system_id}')
        header = HeaderNav(browser, language)
        header.get_log_in_link().invoke()
        login_component = LoginComponent(browser, language)
        login_component.login(cloud_account.user_email, cloud_account.password)
        SystemToolBar(browser).open_bookmarks()
        calendar = Calendar(browser)
        assert calendar.get_current_date() == browser_stand.vm().os_access.get_datetime().date()
        bookmarks_component = BookmarksComponent(browser, language)
        # Thumbnails for newest bookmarks are shown first.
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_2, thumbnail_1] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 2 bookmarks expected, {len(thumbnails)} found")
        expected_info_1 = {
            'start': bookmark_1_start,
            'bookmark_name': bookmark_1_name,
            'camera_name': camera_1.name,
            }
        expected_info_2 = {
            'start': bookmark_2_start,
            'bookmark_name': bookmark_2_name,
            'camera_name': camera_2.name,
            }
        errors_1 = _get_bookmark_info_errors(thumbnail_1.get_info(), expected_info_1)
        assert not errors_1, f"Found bookmark info errors: {errors_1}"
        errors_2 = _get_bookmark_info_errors(thumbnail_2.get_info(), expected_info_2)
        assert not errors_2, f"Found bookmark info errors: {errors_2}"
        calendar.set_date_range(
            bookmark_1_start - timedelta(days=1), bookmark_1_start + timedelta(hours=1))
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_1] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 1 bookmark expected, {len(thumbnails)} found")
        errors_1 = _get_bookmark_info_errors(thumbnail_1.get_info(), expected_info_1)
        assert not errors_1, f"Found bookmark info errors: {errors_1}"
        calendar.set_date_range(
            bookmark_2_start - timedelta(hours=12), bookmark_2_start + timedelta(hours=1))
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_2] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 1 bookmark expected, {len(thumbnails)} found")
        errors_2 = _get_bookmark_info_errors(thumbnail_2.get_info(), expected_info_2)
        assert not errors_2, f"Found bookmark info errors: {errors_2}"
        time_range = TimeRange(browser)
        time_range.set(
            bookmark_2_start + timedelta(minutes=10), bookmark_2_start + timedelta(hours=2))
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        assert not thumbnails, f"Exactly 0 bookmarks expected, {len(thumbnails)} found"
        time_range.set(
            bookmark_2_start - timedelta(minutes=10), bookmark_2_start + timedelta(hours=1))
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_2] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 1 bookmark expected, {len(thumbnails)} found")
        errors_2 = _get_bookmark_info_errors(thumbnail_2.get_info(), expected_info_2)
        assert not errors_2, f"Found bookmark info errors: {errors_2}"
        quick_select = QuickSelect(browser, language)
        quick_select.show_last_day()
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        assert not thumbnails, f"Exactly 0 bookmarks expected, {len(thumbnails)} found"
        quick_select.show_last_7_days()
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_2] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 1 bookmark expected, {len(thumbnails)} found")
        errors_2 = _get_bookmark_info_errors(thumbnail_2.get_info(), expected_info_2)
        assert not errors_2, f"Found bookmark info errors: {errors_2}"
        quick_select.show_last_30_days()
        thumbnails = bookmarks_component.list_bookmark_thumbnails()
        try:
            [thumbnail_2, thumbnail_1] = thumbnails
        except ValueError:
            raise RuntimeError(f"Exactly 2 bookmarks expected, {len(thumbnails)} found")
        errors_1 = _get_bookmark_info_errors(thumbnail_1.get_info(), expected_info_1)
        assert not errors_1, f"Found bookmark info errors: {errors_1}"
        errors_2 = _get_bookmark_info_errors(thumbnail_2.get_info(), expected_info_2)
        assert not errors_2, f"Found bookmark info errors: {errors_2}"


def _get_bookmark_info_errors(
        bookmark_info: _BookmarkInfo,
        expected_info: Mapping[str, Union[datetime, str]],
        ) -> Mapping[str, Mapping[str, Union[str, datetime]]]:
    errors = {}
    expected_start = expected_info['start']
    actual_start = bookmark_info.get_naive_start().replace(tzinfo=expected_start.tzinfo)
    if abs(actual_start - expected_start) > timedelta(minutes=1):
        errors['start'] = {
            'Expected': expected_start,
            'Actual': actual_start,
            }
    expected_bookmark_name = expected_info['bookmark_name']
    actual_bookmark_name = bookmark_info.get_bookmark_name()
    if actual_bookmark_name != expected_bookmark_name:
        errors['bookmark_name'] = {
            'Expected': expected_bookmark_name,
            'Actual': actual_bookmark_name,
            }
    expected_camera_name = expected_info['camera_name']
    actual_camera_name = bookmark_info.get_camera_name()
    if expected_camera_name != actual_camera_name:
        errors['camera_name'] = {
            'Expected': expected_camera_name,
            'Actual': actual_camera_name,
            }
    return errors


if __name__ == '__main__':
    exit(test_bookmark_filters().main())
