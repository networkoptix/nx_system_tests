# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import MediaserverApiHttpError
from mediaserver_api import NotFound
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _try_create_bookmark(actor_api, camera_id):
    credentials = actor_api.get_credentials()
    user = credentials.username
    try:
        bookmark_id = actor_api.add_bookmark(camera_id=camera_id, name=f'bookmark_{user}')
    except (Forbidden, NotFound):
        return None
    return actor_api.get_bookmark(camera_id, bookmark_id)


def _can_edit_bookmark(actor_api, bookmark, duration_ms):
    try:
        actor_api.set_bookmark_duration(bookmark, duration_ms)
    except (Forbidden, NotFound):
        return False
    return True


def _can_remove_bookmark(actor_api, bookmark):
    try:
        actor_api.remove_bookmark(bookmark)
    except (Forbidden, NotFound):
        return False
    except MediaserverApiHttpError as exc:
        # After VMS-37901 it returns 500 in APIv0. According to developers, it is expected
        # (and yet strange).
        if exc.http_status == 500 and 'Can\'t delete bookmark' in exc.vms_error_string:
            return False
        raise
    return True


def _can_see_admin_bookmark(actor_api, bookmark):
    try:
        bookmark_list = actor_api.list_bookmarks(bookmark.camera_id)
    except (Forbidden, NotFound):
        return False
    return bookmark in bookmark_list


def _test_manage_bookmark(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    sample_media_file = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample.mkv'))
    [dummy_camera] = mediaserver.add_cameras_with_archive(
        sample_media_file=sample_media_file,
        start_times=[datetime(2019, 1, 11, tzinfo=timezone.utc)],
        )
    camera_id = dummy_camera.id
    password = 'Irr3levant!'

    test_admin = api.add_local_admin('test_admin', password)
    admin_api = api.as_user(test_admin)
    bookmark_admin = _try_create_bookmark(admin_api, dummy_camera.id)
    bookmark_system_admin = _create_system_admin_bookmark(api, camera_id)
    assert _can_see_admin_bookmark(admin_api, bookmark_system_admin)
    assert _can_edit_bookmark(admin_api, bookmark_admin, duration_ms=120000)
    assert _can_edit_bookmark(admin_api, bookmark_system_admin, duration_ms=120000)
    assert _can_remove_bookmark(admin_api, bookmark_admin)
    assert _can_remove_bookmark(admin_api, bookmark_system_admin)

    test_advanced_viewer = api.add_local_advanced_viewer('test_advanced_viewer', password)
    adv_viewer_api = api.as_user(test_advanced_viewer)
    bookmark_adv_viewer = _try_create_bookmark(adv_viewer_api, dummy_camera.id)
    bookmark_system_admin = _create_system_admin_bookmark(api, camera_id)
    assert _can_see_admin_bookmark(adv_viewer_api, bookmark_system_admin)
    assert _can_edit_bookmark(adv_viewer_api, bookmark_adv_viewer, duration_ms=120000)
    assert _can_edit_bookmark(adv_viewer_api, bookmark_system_admin, duration_ms=120000)
    assert _can_remove_bookmark(adv_viewer_api, bookmark_adv_viewer)
    assert _can_remove_bookmark(adv_viewer_api, bookmark_system_admin)

    bookmark_system_admin = _create_system_admin_bookmark(api, camera_id)
    test_viewer = api.add_local_viewer('test_viewer', password)
    viewer_api = api.as_user(test_viewer)
    assert _can_see_admin_bookmark(viewer_api, bookmark_system_admin)
    assert _try_create_bookmark(viewer_api, dummy_camera.id) is None
    assert not _can_edit_bookmark(viewer_api, bookmark_system_admin, duration_ms=180000)
    assert not _can_remove_bookmark(viewer_api, bookmark_system_admin)

    test_live_viewer = api.add_local_live_viewer('test_live_viewer', password)
    live_viewer_api = api.as_user(test_live_viewer)
    assert not _can_see_admin_bookmark(live_viewer_api, bookmark_system_admin)
    assert _try_create_bookmark(live_viewer_api, dummy_camera.id) is None
    assert not _can_edit_bookmark(live_viewer_api, bookmark_system_admin, duration_ms=180000)
    assert not _can_remove_bookmark(live_viewer_api, bookmark_system_admin)


def _create_system_admin_bookmark(api, camera_id):
    bookmark_id = api.add_bookmark(camera_id=camera_id, name='test_bookmark')
    return api.get_bookmark(camera_id, bookmark_id)
