# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_analytic_events_basic_checks(VMSTest):
    """Analytic events basic checks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26616

    Selection-Tag: 26616
    Selection-Tag: analytics
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client_with_analytics_plugins(['sample']))
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        # 5000 ms is the minimal available interval.
        client_installation.set_ini('nx_vms_client_core.ini', {'cameraDataLoadingIntervalMs': '5000'})
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.start_recording(test_camera_1.id)
        testkit_api, camera_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        right_panel = RightPanelWidget(testkit_api, hid)
        assert not right_panel.objects_tab_is_accessible()
        with camera_item.open_context_menu().open_camera_settings() as camera_settings:
            camera_settings.activate_integrations_tab()
            camera_settings.plugins_tab.enable_plugin("Sample")
            assert camera_settings.plugins_tab.plugin_is_enabled("Sample")
        error_tile = NotificationsRibbon(testkit_api, hid).get_tile_by_name("Issue with Analytics Plugin detected")
        assert error_tile is None
        assert right_panel.objects_tab_is_accessible()
        assert not Timeline(testkit_api, hid).get_analytics_archive_chunks()
        right_panel.open_objects_tab()
        assert right_panel.objects_tab.has_tiles_within_timeout()
        bounding_boxes = camera_item.get_bounding_boxes_within_timeout()
        # In some rare cases two bounding boxes can appear for the object.
        # It happens when old track is about to end and the new track has just started.
        assert len(bounding_boxes) in [1, 2]
        assert Timeline(testkit_api, hid).get_analytics_archive_chunks_within_timeout()


if __name__ == '__main__':
    exit(test_analytic_events_basic_checks().main())
