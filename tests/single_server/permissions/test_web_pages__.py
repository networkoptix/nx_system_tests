# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.permissions.common import get_api_for_actor


def _try_add_web_page(actor_api):
    credentials = actor_api.get_credentials()
    user = credentials.username
    try:
        web_page_id = actor_api.add_web_page(
            f'test_web_page_added_by_user_{user}', 'http://www.networkoptix.com/')
    except Forbidden:
        return None
    return actor_api.get_web_page(web_page_id)


def _can_edit_web_page(actor_api, web_page_id, url):
    try:
        actor_api.modify_web_page(web_page_id, url)
    except Forbidden:
        return False
    return True


def _can_remove_web_page(actor_api, web_page_id):
    try:
        actor_api.remove_resource(web_page_id)
    except Forbidden:
        return False
    return True


def _test_manage_web_pages(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    test_http_server = create_test_http_server('page_with_link')
    exit_stack.enter_context(test_http_server)
    mediaserver_source_address = one_mediaserver.mediaserver().os_access.source_address()
    test_http_server2 = create_test_http_server('dropdown_page')
    exit_stack.enter_context(test_http_server2)
    test_http_server3 = create_test_http_server('page_with_tabs')
    exit_stack.enter_context(test_http_server3)

    def _add_system_admin_web_page():
        web_page_id = api.add_web_page(
            'test_web_page_created_by_system_admin',
            f'http://{mediaserver_source_address}:{test_http_server.server_port}',
            )
        return api.get_web_page(web_page_id)

    admin_api = get_api_for_actor(api, 'admin')
    web_page_admin = _try_add_web_page(admin_api)
    web_page_system_admin = _add_system_admin_web_page()
    assert web_page_system_admin in admin_api.list_web_pages()
    link2 = f'http://{mediaserver_source_address}:{test_http_server2.server_port}'
    assert _can_edit_web_page(admin_api, web_page_admin.id, link2)
    assert _can_edit_web_page(admin_api, web_page_system_admin.id, link2)
    assert _can_remove_web_page(admin_api, web_page_admin.id)
    assert _can_remove_web_page(admin_api, web_page_system_admin.id)

    web_page_system_admin = _add_system_admin_web_page()
    adv_viewer_api = get_api_for_actor(api, 'advanced_viewer')
    assert web_page_system_admin in adv_viewer_api.list_web_pages()
    assert _try_add_web_page(adv_viewer_api) is None
    link3 = f'http://{mediaserver_source_address}:{test_http_server3.server_port}'
    assert not _can_edit_web_page(adv_viewer_api, web_page_system_admin.id, link3)
    assert not _can_remove_web_page(adv_viewer_api, web_page_system_admin.id)

    viewer_api = get_api_for_actor(api, 'viewer')
    assert web_page_system_admin in viewer_api.list_web_pages()
    assert _try_add_web_page(viewer_api) is None
    assert not _can_edit_web_page(viewer_api, web_page_system_admin.id, link3)
    assert not _can_remove_web_page(viewer_api, web_page_system_admin.id)

    live_viewer_api = get_api_for_actor(api, 'live_viewer')
    assert web_page_system_admin in live_viewer_api.list_web_pages()
    assert _try_add_web_page(live_viewer_api) is None
    assert not _can_edit_web_page(live_viewer_api, web_page_system_admin.id, link3)
    assert not _can_remove_web_page(live_viewer_api, web_page_system_admin.id)
