# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_client_with_web_page_open
from gui.desktop_ui.dialogs.edit_webpage import suppress_connect_anyway
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.scene_items import IntegrationSceneItem
from gui.gui_test_stand import GuiTestStand
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_integration_with_enabled_client_api(VMSTest):
    """Integrations basic checks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85377

    Selection-Tag: 85377
    Selection-Tag: webpages
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_VM, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('desktop_client.ini', {'hideOtherSystemsFromResourceTree': 'true'})
        test_http_server = create_test_http_server('js_api_web_page_compatible')
        exit_stack.enter_context(test_http_server)
        test_page_url = f'http://{client_installation.os_access.source_address()}:{test_http_server.server_port}'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_VM.os_access, 'samples/overlay_test_video.mp4'))
        [camera] = server_VM.api.add_test_cameras(0, 1)
        [web_page_item, testkit_api, hid] = start_client_with_web_page_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_VM),
            machine_pool.get_testkit_port(),
            client_installation,
            server_VM,
            test_page_url,
            )
        web_page_item.wait_for_phrase_exists('TEST')
        assert not web_page_item.has_phrase(camera.name)
        LayoutTabBar(testkit_api, hid).close_current_layout()
        web_page_item.wait_for_inaccessible()
        dialog = MainMenu(testkit_api, hid).activate_new_integration()
        integration_name = 'INTEGRATION'
        dialog.create_resource(
            url=test_page_url,
            name=integration_name,
            )
        suppress_connect_anyway(testkit_api, hid)
        integration_item = IntegrationSceneItem(testkit_api, hid, integration_name)
        integration_item.wait_for_accessible()
        integration_item.wait_for_phrase_exists('TEST')
        assert integration_item.has_phrase(camera.name)
        dummy_page_name = 'DUMMY'
        assert not integration_item.has_phrase(dummy_page_name)
        server_VM.api.add_web_page(dummy_page_name, 'https://some_dummy_url.com')
        integration_item.wait_for_phrase_exists(dummy_page_name)
        integration_item.click_on_phrase(f'{integration_name} [web_page] geometry')
        integration_item.click_on_phrase("REMOVE")
        integration_item.wait_for_inaccessible()


if __name__ == '__main__':
    exit(test_integration_with_enabled_client_api().main())
