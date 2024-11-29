# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.event_log import get_event_log_dialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.analytics.common import enable_device_agent
from tests.base_test import VMSTest


class test_check_stub_analytics_event(VMSTest):
    """Stub plugin events subplugin basic checks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26620

    Selection-Tag: 26620
    Selection-Tag: analytics
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client_with_analytics_plugins(['stub']))
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        # Disable rules 'On Network Issue' as the event may appear and displace test events.
        event_rules = server_vm.api.list_event_rules()
        for rule in event_rules:
            if rule.data['eventType'] == 'networkIssueEvent':
                server_vm.api.disable_event_rule(UUID(rule.data['id']))
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        events_engine = server_vm.api.get_analytics_engine_collection().get_stub('Events')
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
        # Each tile may take up to 5 seconds to handle, and it's better to close unused ones.
        right_panel.notifications_ribbon.close_all_tiles()
        enable_device_agent(server_vm.api, events_engine.name(), test_camera_1.id)
        # TODO: Set up event rule via API.
        site_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        event_rules_dialog = site_administration_dialog.open_event_rules()
        add_rule_dialog = event_rules_dialog.get_add_rule_dialog()
        event_gui = add_rule_dialog.get_analytics_event()
        event_gui.set_cameras([test_camera_1.name])
        add_rule_dialog.get_desktop_notification_action()
        event_gui.set_analytics_event_type('Line crossing')
        add_rule_dialog.save_and_close()
        event_rules_dialog.close()
        site_administration_dialog.close()
        # Sometimes when the dates are different on Client and Server machines, the full date
        # is written in the top of the notification, opposed to the regular behavior when only
        # time is written. This causes the problem with the event name in the notification:
        # it doesn't fit and gets cropped. So we can look for a desired notification by
        # its description rather than name: the description is always the same.
        right_panel.notifications_ribbon.wait_for_notification_with_description(
            "Line crossing - impulse event (description)", timeout_sec=30)
        hid.keyboard_hotkeys('Ctrl', 'L')
        current_description = get_event_log_dialog(testkit_api, hid).get_description_of_event_with_action(
            event="Line crossing",
            action="Show desktop notification",
            )
        assert current_description == "Line crossing - impulse event (caption): Line crossing - impulse event (description)"


if __name__ == '__main__':
    exit(test_check_stub_analytics_event().main())
