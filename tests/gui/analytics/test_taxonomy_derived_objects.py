# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.dialogs.advanced_object_search import AnalyticObjectTypesNames
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_taxonomy_derived_objects(VMSTest):
    """Check Stub taxonomy derived object filters.

    There is no test in TestRail to check Stub: Taxonomy Features filters. So no link is provided.

    Selection-Tag: analytics
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client_with_analytics_plugins(['stub']))
        server_vm.api.set_license_server(license_server.url())
        grant_license(server_vm, license_server)
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
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

        # Check Stub: Base Object 1.
        type_name = AnalyticObjectTypesNames.base1.value
        advanced_dialog.click_object_type_button(type_name)
        advanced_dialog.wait_for_tiles_with_title(type_name)

        derived_type_name = "Stub: Derived Object Type"
        advanced_dialog.click_object_type_button(derived_type_name)
        filter_blocks = advanced_dialog.get_all_filter_blocks()
        boolean_block = filter_blocks["(Base) Boolean attribute"]
        boolean_buttons = boolean_block.get_radiobuttons_with_names()
        hid.mouse_left_click_on_object(boolean_buttons['No'])
        advanced_dialog.wait_for_no_tiles_with_title(derived_type_name)
        hid.mouse_left_click_on_object(boolean_buttons['Yes'])
        advanced_dialog.wait_for_no_tiles_with_title(type_name)
        advanced_dialog.wait_for_tiles_with_title(derived_type_name)
        enum_block = filter_blocks["(Base) Enum attribute"]
        enum_block.click_header()
        color_block = filter_blocks["(Base) Color attribute"]
        color_block.click_header()
        object_attribute_block = filter_blocks["(Base) Object attribute"]
        object_attribute_block.click_header()

        derived_type_block = filter_blocks["(Derived) attribute 1"]
        string_field = derived_type_block.get_string_attribute_field()
        string_field.type_text('lalala')
        advanced_dialog.wait_for_no_tiles_with_title(derived_type_name)
        string_field.type_text('attribute 1 value')
        advanced_dialog.wait_for_tiles_with_title(derived_type_name)

        advanced_dialog.click_object_type_button(derived_type_name)
        omitted_attributes_object_type = "Stub: Derived Object Type with omitted attributes"
        advanced_dialog.click_object_type_button(omitted_attributes_object_type)
        advanced_dialog.wait_for_tiles_with_title(omitted_attributes_object_type)
        filter_blocks = advanced_dialog.get_all_filter_blocks()
        number_attribute_name = "(Base) Number attribute"
        base_string_attribute_name = "(Base) String attribute"
        derived_own_attribute = "(Derived) own attribute"
        assert number_attribute_name not in filter_blocks, (
            f"{number_attribute_name} found among {filter_blocks}")
        assert base_string_attribute_name in filter_blocks, (
            f"{base_string_attribute_name} not found among {filter_blocks}")
        assert derived_own_attribute in filter_blocks, (
            f"{derived_own_attribute} not found among {filter_blocks}")


if __name__ == '__main__':
    exit(test_taxonomy_derived_objects().main())
