# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.webdriver import ElementNotFound
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.dialogs.advanced_object_search import AdvancedObjectSearchDialog
from gui.desktop_ui.dialogs.advanced_object_search import AnalyticObjectTypesNames
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.widget import Widget
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_taxonomy_object_types(VMSTest):
    """Check Stub taxonomy object types.

    There is no test in TestRail to check Stub: Taxonomy Features filters. So no link is provided.

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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.start_recording(test_camera_1.id)
        engine_collection = server_vm.api.get_analytics_engine_collection()
        taxonomy_plugin = engine_collection.get_stub('Taxonomy Features')
        server_vm.api.enable_device_agent(taxonomy_plugin, test_camera_1.id)
        testkit_api, camera_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        camera_node = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name)
        camera_settings = camera_node.open_settings()
        camera_settings.activate_integrations_tab()
        camera_settings.plugins_tab.open_device_agent_settings(taxonomy_plugin.name())
        plugin_checkboxes = camera_settings.plugins_tab.get_checkboxes()
        expected_checkboxes_names = [
            "Base Object Type",
            "Derived Object Type",
            "Derived Object Type with own attributes",
            "Hidden derived Object Type",
            "Hidden derived Object Type with own attributes",
            "Derived Object Type with unsupported base",
            "Object Type with numeric attributes",
            "Object Type with boolean attributes",
            "Object Type with icon",
            "Object Type inherited from the Base Type Library type",
            "Object Type with Base Type Library Enum attribute",
            "Object Type with Base Type Library Color attribute",
            "Object Type with Base Type Library Object attribute",
            "Base Type Library Object Type",
            "Object Type declared in the Engine manifest",
            "Live-only Object Type",
            "Non-indexable Object Type",
            "Extended Object Type",
            "Object Type with Attribute List",
            ]
        if server_vm.newer_than('vms_6.0'):
            expected_checkboxes_names.append('Object Type with dependent attributes')
            expected_checkboxes_names.append('Object Type with Enum attributes with inline items')
        current_checkboxes_names = []
        for checkbox in plugin_checkboxes:
            checkbox_text = checkbox.get_text()
            assert checkbox.is_checked(), f"{checkbox_text} should be checked"
            current_checkboxes_names.append(checkbox_text)
        assert sorted(expected_checkboxes_names) == sorted(current_checkboxes_names), (
            f"{sorted(expected_checkboxes_names)} != {sorted(current_checkboxes_names)}")
        right_panel = RightPanelWidget(testkit_api, hid)
        right_panel.open_objects_tab()
        advanced_dialog = right_panel.objects_tab.open_advanced_object_search_dialog()
        advanced_dialog.wait_until_appears()

        # Check all Object Types existence.
        person_type_name = AnalyticObjectTypesNames.person.value
        animal_type_name = AnalyticObjectTypesNames.animal.value
        assert _has_object_type_button(advanced_dialog, person_type_name)
        assert _has_object_type_button(advanced_dialog, animal_type_name)
        assert _has_object_type_button(advanced_dialog, AnalyticObjectTypesNames.base1.value)
        assert _has_object_type_button(advanced_dialog, AnalyticObjectTypesNames.base2.value)
        assert _has_object_type_button(advanced_dialog, AnalyticObjectTypesNames.live_only.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.non_indexable.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.from_engine_manifest.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.custom_with_base_color_type.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.custom_with_base_enum_type.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.custom_with_base_object_type.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.with_attribute_list.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.with_boolean_attributes.value)
        assert _has_object_type_button(
            advanced_dialog, AnalyticObjectTypesNames.with_numeric_attributes.value)

        # Check Stub: Object Type with icon.
        default_icon = advanced_dialog.get_object_type_icon(person_type_name).image_capture()
        car_icon = advanced_dialog.get_object_type_icon(AnalyticObjectTypesNames.with_icon.value).image_capture()
        assert not default_icon.is_similar_to(car_icon)

        # Check Person Object Type.
        advanced_dialog.click_object_type_button(person_type_name)
        animal_type_filter = advanced_dialog.get_object_type_button_object(animal_type_name)
        assert _no_filter_button_within_timeout(animal_type_filter)
        inherited_type_name = "Stub: Object Type inherited from a Base Type Library Type"
        advanced_dialog.wait_for_tiles_with_title(inherited_type_name)


def _no_filter_button_within_timeout(filter_button: Widget) -> bool:
    start_time = time.monotonic()
    timeout = 3
    while True:
        if not filter_button.is_accessible_timeout(timeout=1):
            return True
        if time.monotonic() - start_time > timeout:
            return False


def _has_object_type_button(advanced_dialog: AdvancedObjectSearchDialog, type_name: str) -> bool:
    try:
        advanced_dialog.get_object_type_button_object(type_name)
    except ElementNotFound:
        return False
    return True


if __name__ == '__main__':
    exit(test_taxonomy_object_types().main())
