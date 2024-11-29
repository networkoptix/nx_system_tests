# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_proxy_image_server
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.analytics_plugins.stub_settings import ActiveSettingsDialog
from gui.desktop_ui.analytics_plugins.stub_settings import ActiveSettingsSection
from gui.desktop_ui.analytics_plugins.stub_settings import WebDialog
from gui.desktop_ui.dialogs.edit_webpage import suppress_connect_anyway
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from os_access import current_host_address
from tests.base_test import VMSTest


class test_check_stub_settings(VMSTest):
    """Check Stub active settings.

    There is no test in TestRail to check Active Settings section of Stub: Settings.
    So no link is provided.

    Selection-Tag: analytics
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_VM, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_with_analytics_plugins(['stub']))
        server_VM.allow_license_server_access(license_server.url())
        api = server_VM.api
        api.set_license_server(license_server.url())
        api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': api.get_brand(),
            }))
        exit_stack.enter_context(playing_testcamera(machine_pool, server_VM.os_access, 'samples/overlay_test_video.mp4'))
        [camera] = api.add_test_cameras(0, 1)
        gui_machine_address = '127.0.0.1'
        test_http_server = exit_stack.enter_context(
            create_proxy_image_server(
                ip_addresses_to_check_proxy=[gui_machine_address],
                source_address_from_client=client_installation.os_access.source_address(),
                ))
        test_page_url = f'https://{current_host_address()}:{test_http_server.server_port}/'
        [testkit_api, camera_item] = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_VM),
            machine_pool.get_testkit_port(),
            client_installation,
            server_VM,
            camera.name,
            )
        hid = HID(testkit_api)
        camera_settings = camera_item.open_context_menu().open_camera_settings()
        camera_settings.activate_integrations_tab()
        engine_collection = api.get_analytics_engine_collection()
        engine = engine_collection.get_stub('Settings')
        tab = camera_settings.plugins_tab
        tab.enable_plugin(engine.name())
        camera_settings.apply_changes()
        active_settings = ActiveSettingsSection(testkit_api, hid)
        active_settings.open()
        initial_settings = api.get_device_analytics_settings(camera.id, engine.id()).values
        assert not initial_settings['activeCheckBox']
        assert 'additionalComboBox' not in initial_settings
        assert not active_settings.has_combobox_within_timeout("Additional ComboBox", timeout=0)
        active_settings.get_active_combobox_with_label_text("Active ComboBox").select("Show additional ComboBox")
        assert active_settings.has_combobox_within_timeout("Additional ComboBox")
        api_settings = api.get_device_analytics_settings(camera.id, engine.id()).values
        assert 'additionalComboBox' in api_settings
        active_settings.click_active_checkbox()
        settings_dialog = ActiveSettingsDialog(testkit_api, hid)
        settings_dialog.wait_for_accessible()
        settings_dialog.close_by_ok()
        settings_dialog.wait_for_inaccessible()
        initial_gui_radiobuttons = active_settings.get_radiobutton_collection()
        assert initial_settings['activeRadioButtonGroup'] == "Some value"
        expected_buttons = ["Some value", "Show something"]
        assert initial_gui_radiobuttons.get_sorted_names() == sorted(expected_buttons)
        hid.mouse_left_click_on_object(initial_gui_radiobuttons.get_button("Show something"))
        new_gui_radiobuttons = active_settings.get_radiobutton_collection()
        expected_buttons_long = ["Some value", "Show something", "Hide me"]
        assert new_gui_radiobuttons.get_sorted_names() == sorted(expected_buttons_long)
        hid.mouse_left_click_on_object(new_gui_radiobuttons.get_button("Hide me"))
        new_short_gui_radiobuttons = active_settings.get_radiobutton_collection()
        assert new_short_gui_radiobuttons.get_sorted_names() == sorted(expected_buttons)
        show_message_button = active_settings.get_show_message_button()
        show_message_button.wait_for_accessible()
        hid.mouse_left_click_on_object(show_message_button)
        dialog = ActiveSettingsDialog(testkit_api, hid)
        dialog.wait_for_accessible()
        dialog.get_text_field().type_text("Itsy Bitsy Spider")
        dialog.close_by_ok()
        dialog.wait_for_inaccessible()
        box = MessageBox(testkit_api, hid).wait_until_appears()
        title = box.get_title()
        assert title == 'Message Example. \nParameter: "Itsy Bitsy Spider"'
        box.close_by_button("OK")
        active_minimum = active_settings.get_active_minimum_spinbox()
        active_maximum = active_settings.get_active_maximum_spinbox()
        assert initial_settings['activeMinValue'] == 42
        assert initial_settings['activeMaxValue'] == 42
        assert active_minimum.get_text() == "42"
        assert active_maximum.get_text() == "42"
        assert active_minimum.down_arrow().is_enabled()
        assert not active_minimum.up_arrow().is_enabled()
        assert active_maximum.up_arrow().is_enabled()
        assert not active_maximum.down_arrow().is_enabled()
        active_minimum.set(42, 40)
        active_maximum = active_settings.get_active_maximum_spinbox()
        assert active_maximum.up_arrow().is_enabled()
        assert active_maximum.down_arrow().is_enabled()
        active_maximum.set(42, 40)
        camera_settings.apply_changes()
        assert active_maximum.up_arrow().is_enabled()
        assert not active_maximum.down_arrow().is_enabled()
        camera_settings.apply_changes()
        camera_settings.get_apply_button().wait_for_inaccessible()
        new_api_settings = api.get_device_analytics_settings(camera.id, engine.id()).values
        assert new_api_settings['activeCheckBox']
        assert new_api_settings['activeRadioButtonGroup'] == "Some value"
        assert new_api_settings['activeMinValue'] == 40
        assert new_api_settings['activeMaxValue'] == 40
        active_settings.get_field().type_text(test_page_url)
        show_webpage_button = active_settings.get_show_webpage_button()
        hid.mouse_left_click_on_object(show_webpage_button)
        dialog = WebDialog(testkit_api)
        suppress_connect_anyway(testkit_api, hid)
        dialog.wait_for_phrase_exists("APPLE")
        assert dialog.has_phrase("LOCO")
        hid.mouse_left_click_on_object(dialog.get_ok_button())
        dialog.wait_until_closed()


if __name__ == '__main__':
    exit(test_check_stub_settings().main())
