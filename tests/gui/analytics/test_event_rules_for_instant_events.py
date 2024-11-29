# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_event_rules_for_instant_events(VMSTest):
    """Event rules for instant events.

    Selection-Tag: 26619
    Selection-Tag: analytics
    Selection-Tag: gui-smoke-test
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26619
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_with_analytics_plugins(['sample']))
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        exit_stack.enter_context(
            playing_testcamera(
                machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.start_recording(test_camera_1.id)
        [testkit_api, camera_item] = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        right_panel = RightPanelWidget(testkit_api, hid)
        assert right_panel.has_button('events')
        assert right_panel.has_button('motion')
        assert right_panel.has_button('bookmarks')
        assert not right_panel.objects_tab_is_accessible()

        engine_collection = server_vm.api.get_analytics_engine_collection()
        sample_plugin = engine_collection.get_by_exact_name('Sample')
        server_vm.api.enable_device_agent(sample_plugin, test_camera_1.id)
        assert right_panel.has_button('events')
        assert right_panel.has_button('motion')
        assert right_panel.has_button('bookmarks')
        assert right_panel.has_button('objects')
        right_panel.open_objects_tab()
        right_panel.objects_tab.wait_for_tiles()
        camera_item.close()
        assert not right_panel.objects_tab.tile_loaders()
        advanced_dialog = right_panel.objects_tab.open_advanced_object_search_dialog()
        advanced_dialog.wait_until_appears()
        object_name = 'Hello, World!'
        assert not advanced_dialog.get_tiles_with_text(object_name)
        advanced_dialog.click_filter_with_text('Cameras on layout')
        advanced_dialog.set_filter_any_camera()
        advanced_dialog.wait_for_tiles_with_title(object_name)
        hid.mouse_left_click_on_object(advanced_dialog.get_tiles_with_text(object_name)[0])
        hid.mouse_left_click_on_object(advanced_dialog.get_show_on_layout_button())
        advanced_dialog.close()
        right_panel.objects_tab.wait_for_tiles()


if __name__ == '__main__':
    exit(test_event_rules_for_instant_events().main())
