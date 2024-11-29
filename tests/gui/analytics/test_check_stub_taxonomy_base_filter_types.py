# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.dialogs.advanced_object_search import AnalyticObjectTypesNames
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import NumberInput
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_check_stub_taxonomy_base_filter_types(VMSTest):
    """Check Stub taxonomy filters.

    There is no test in TestRail to check Stub: Taxonomy Features filters. So no link is provided.

    Selection-Tag: analytics
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_with_analytics_plugins(['stub']))
        server_vm.api.set_license_server(license_server.url())
        grant_license(server_vm, license_server)
        exit_stack.enter_context(playing_testcamera(
            machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.start_recording(test_camera_1.id)
        engine_collection = server_vm.api.get_analytics_engine_collection()
        taxonomy_plugin = engine_collection.get_stub('Taxonomy Features')
        server_vm.api.enable_device_agent(taxonomy_plugin, test_camera_1.id)
        [testkit_api, _camera_item] = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        right_panel = RightPanelWidget(testkit_api, hid)
        right_panel.open_objects_tab()
        advanced_dialog = right_panel.objects_tab.open_advanced_object_search_dialog()
        advanced_dialog.wait_until_appears()

        # Check Person Object Type.
        person_type_name = AnalyticObjectTypesNames.person.value
        advanced_dialog.click_object_type_button(person_type_name)
        animal_type_name = AnalyticObjectTypesNames.animal.value
        animal_type_filter = advanced_dialog.get_object_type_button_object(animal_type_name)
        assert no_filter_button_within_timeout(animal_type_filter)
        inherited_type_name = "Stub: Object Type inherited from a Base Type Library Type"
        advanced_dialog.click_object_type_button(inherited_type_name)
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        filter_blocks = advanced_dialog.get_all_filter_blocks()
        gender_buttons = filter_blocks["Gender"].get_radiobuttons_with_names()
        expected_genders = ["Man", "Other", "Woman"]
        assert expected_genders == sorted((gender_buttons.keys())), (
            f"{expected_genders} != {sorted(gender_buttons.keys())}")
        hid.mouse_left_click_on_object(gender_buttons["Other"])
        advanced_dialog.wait_for_no_tiles_with_title(inherited_type_name)
        hid.mouse_left_click_on_object(gender_buttons["Man"])
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        filter_blocks["Gender"].click_header()
        [from_field, to_field] = filter_blocks["Height, cm"].get_number_attribute_fields()
        from_field.type_number(190)
        advanced_dialog.wait_for_no_tiles_with_title(inherited_type_name)
        from_field.type_number(100)
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        expected_to = 170
        to_field.type_number(expected_to)
        _wait_for_numeric_input(to_field, expected_to)
        advanced_dialog.wait_for_no_tiles_with_title(inherited_type_name)
        to_field.type_number(190)
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        filter_blocks["Height, cm"].click_header()
        filter_blocks["Hat"].click_header()
        color_buttons = filter_blocks["Top Clothing Color"].get_radiobuttons_with_names()
        expected_colors = [
            "Black",
            "Blue",
            "Brown",
            "Gray",
            "Green",
            "Orange",
            "Red",
            "Violet",
            "White",
            "Yellow",
            ]
        assert expected_colors == sorted(color_buttons.keys()), (
            f"{expected_colors} != {sorted(color_buttons.keys())}")
        hid.mouse_left_click_on_object(color_buttons["Violet"])
        advanced_dialog.wait_for_no_tiles_with_title(inherited_type_name)
        hid.mouse_left_click_on_object(color_buttons["Yellow"])
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        filter_blocks["Top Clothing Color"].click_header()
        name_field = filter_blocks["Name"].get_string_attribute_field()
        name_field.type_text("Pushkin")
        advanced_dialog.wait_for_no_tiles_with_title(inherited_type_name)
        name_field.type_text("John")
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)
        advanced_dialog.click_object_type_button(person_type_name)


def no_filter_button_within_timeout(filter_button: Widget) -> bool:
    start_time = time.monotonic()
    timeout = 3
    while True:
        if not filter_button.is_accessible_timeout(timeout=1):
            return True
        if time.monotonic() - start_time > timeout:
            return False


def _wait_for_numeric_input(number_input: NumberInput, expected_value: int):
    started_at = time.monotonic()
    timeout = 3
    while True:
        to_field_value = int(number_input.get_value())
        if to_field_value == expected_value:
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Expected {expected_value}, got {to_field_value}. "
                "Can be caused by a known bug on master branch when 'to' field value is filled the "
                "same as 'from' and cannot be replaced by the new value, "
                "only new numbers can be added to the end. "
                "See: https://networkoptix.atlassian.net/browse/VMS-56216")
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_check_stub_taxonomy_base_filter_types().main())
