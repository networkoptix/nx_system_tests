# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.gui_test_stand import GuiTestStand
from gui.mobile_ui.app_window import ApplicationWindow
from gui.mobile_ui.connect_to_server import ConnectToServer
from gui.mobile_ui.scene import Scene
from gui.mobile_ui.warning_dialog import WarningDialog
from gui.mobile_ui.welcome_screen import WelcomeScreen
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_layout
from mediaserver_api import generate_layout_item
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_layouts(VMSTest):
    """Test Layouts.

    Selection-Tag: 6810
    Selection-Tag: mobile-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6810
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6712

    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        installer_supplier.distrib().assert_not_older_than('vms_6.1', "Mobile tests only supported by VMS 6.1 and newer")
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        server_vm = exit_stack.enter_context(machine_pool.setup_one_server())
        exit_stack.enter_context(similar_playing_testcameras(
            machine_pool=machine_pool,
            os_access=server_vm.os_access,
            primary_prerequisite='samples/overlay_test_video.mp4',
            count=3,
            ))

        [test_camera_1, test_camera_2, test_camera_3] = server_vm.api.add_test_cameras(0, 3)
        layout_1_name = 'layout_1'
        server_vm.api.add_layout_with_resource(layout_1_name, test_camera_1.id)
        layout_item_2 = generate_layout_item(2, str(test_camera_2.id))
        layout_item_3 = generate_layout_item(3, str(test_camera_3.id))
        generated_layout_data = generate_layout(
            index=2,
            items=[layout_item_2, layout_item_3],
            )
        layout_2_name = generated_layout_data.get('name')
        server_vm.api.add_generated_layout(generated_layout_data)
        empty_layout_generated_data = generate_layout(index=3)
        empty_layout_name = empty_layout_generated_data.get('name')
        server_vm.api.add_generated_layout(empty_layout_generated_data)
        mobile_client_installation = exit_stack.enter_context(machine_pool.prepared_mobile_client())
        [testkit_api, hid] = mobile_client_installation.start()

        [server_ip, server_port] = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        WelcomeScreen(testkit_api, hid).click_connect_button()
        owner_credentials = server_vm.api.get_credentials()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=owner_credentials.username,
            password=owner_credentials.password,
            )
        WarningDialog(testkit_api, hid).click_button('Connect')
        Scene(testkit_api, hid).wait_for_accessible()
        app_window = ApplicationWindow(testkit_api, hid)
        # https://networkoptix.testrail.net/index.php?/cases/view/6810
        left_panel = app_window.open_left_panel_widget()
        root_layout_name = 'All Cameras'
        actual_root_layout_item_count = left_panel.get_layout(root_layout_name).get_resource_count()
        expected_root_layout_item_count = 3
        assert actual_root_layout_item_count == expected_root_layout_item_count, (
            f'Expected resource count for {root_layout_name!r}: {expected_root_layout_item_count}'
            f'Actual label value: {actual_root_layout_item_count}'
            )
        actual_layout_1_item_count = left_panel.get_layout(layout_1_name).get_resource_count()
        expected_layout_1_item_count = 1
        assert actual_root_layout_item_count == expected_root_layout_item_count, (
            f'Expected resource count for {layout_1_name!r}: {expected_layout_1_item_count}'
            f'Actual label value: {actual_layout_1_item_count}'
            )
        actual_layout_2_item_count = left_panel.get_layout(layout_2_name).get_resource_count()
        expected_layout_2_item_count = 2
        assert actual_root_layout_item_count == expected_root_layout_item_count, (
            f'Expected resource count for {layout_2_name!r}: {expected_layout_2_item_count}'
            f'Actual label value: {actual_layout_2_item_count}'
            )
        actual_layout_3_item_count = left_panel.get_layout(empty_layout_name).get_resource_count()
        expected_layout_3_item_count = 0
        assert actual_root_layout_item_count == expected_root_layout_item_count, (
            f'Expected resource count for {empty_layout_name!r}: {expected_layout_3_item_count}'
            f'Actual label value: {actual_layout_3_item_count}'
            )
        layouts = left_panel.get_layout_nodes()
        layout_names = [layout.name() for layout in layouts]
        expected_layout_count = 4
        assert len(layout_names) == expected_layout_count, f'Expected layout count: {expected_layout_count}. Actual layouts: {layout_names}'
        assert root_layout_name in layout_names, f"{root_layout_name!r} layout should exist. Actual layout names: {layout_names}"
        assert layout_1_name in layout_names, f'{layout_1_name!r} should exist. Actual layout names: {layout_names}'
        assert layout_2_name in layout_names, f'{layout_2_name!r} should exist. Actual layout names: {layout_names}'

        left_panel.open_layout(layout_1_name)
        layout_1_scene = Scene(testkit_api, hid)
        layout_1_cameras = layout_1_scene.get_camera_items()
        layout_1_expected_item_count = 1
        assert len(layout_1_cameras) == layout_1_expected_item_count, (
            f'Expected layout items count: {layout_1_expected_item_count}.'
            f'Actual items: {layout_1_cameras}'
            )
        [layout_1_item] = layout_1_cameras
        actual_item_name = layout_1_item.name()
        assert test_camera_1.name == actual_item_name, (
            f'Expected scene item name: {test_camera_1.name!r}.'
            f'Actual: {actual_item_name!r}'
            )
        actual_title_text = layout_1_scene.get_title_text()
        assert actual_title_text == layout_1_name, (
            f'Expected scene title: {layout_1_name!r}.'
            f'Actual: {actual_title_text!r}'
            )

        app_window.open_left_panel_widget().open_layout(layout_2_name)
        layout_2_scene = Scene(testkit_api, hid)
        layout_2_cameras = layout_2_scene.get_camera_items()
        layout_2_expected_item_count = 2
        assert len(layout_2_cameras) == layout_2_expected_item_count, (
            f'Expected layout items count: {layout_2_expected_item_count}.'
            f'Actual items: {layout_2_cameras}'
            )
        expected_layout_2_item_names = [test_camera_2.name, test_camera_3.name]
        actual_layout_2_item_names = [item.name() for item in layout_2_cameras]
        assert sorted(expected_layout_2_item_names) == sorted(actual_layout_2_item_names), (
            f'Expected layouts: {expected_layout_2_item_names}.'
            f'Actual layouts: {actual_layout_2_item_names}'
            )
        actual_title_text = layout_2_scene.get_title_text()
        assert actual_title_text == layout_2_name, (
            f'Expected scene title: {layout_2_name!r}.'
            f'Actual: {actual_title_text!r}'
            )

        app_window.open_left_panel_widget().open_layout('All Cameras')
        all_cameras_layout_scene_1 = Scene(testkit_api, hid)
        all_cameras_layout_cameras_1 = all_cameras_layout_scene_1.get_camera_items()
        all_cameras_layout_expected_item_count = 3
        assert len(all_cameras_layout_cameras_1) == all_cameras_layout_expected_item_count, (
            f'Expected layout items count: {all_cameras_layout_expected_item_count}.'
            f'Actual items: {all_cameras_layout_cameras_1}'
            )
        expected_all_cameras_layout_item_names = [
            test_camera_1.name,
            test_camera_2.name,
            test_camera_3.name,
            ]
        actual_all_cameras_layout_item_names_1 = [item.name() for item in all_cameras_layout_cameras_1]
        assert sorted(expected_all_cameras_layout_item_names) == sorted(actual_all_cameras_layout_item_names_1), (
            f'Expected layouts: {expected_all_cameras_layout_item_names}.'
            f'Actual layouts: {actual_all_cameras_layout_item_names_1}'
            )
        actual_title_text = all_cameras_layout_scene_1.get_title_text()
        system_name = server_vm.api.get_system_name()
        assert actual_title_text == system_name, (
            f'Expected scene title: {system_name!r}.'
            f'Actual: {actual_title_text!r}'
            )

        # https://networkoptix.testrail.net/index.php?/cases/view/6712
        app_window.open_left_panel_widget().open_layout(empty_layout_name)
        layout_3_scene = Scene(testkit_api, hid)
        layout_3_cameras = layout_3_scene.get_camera_items()
        layout_3_expected_item_count = 0
        assert len(layout_3_cameras) == layout_3_expected_item_count, (
            f'Expected layout items count: {layout_3_expected_item_count}.'
            f'Actual items: {layout_3_cameras}'
            )
        layout_3_scene_placeholder_text = layout_3_scene.get_placeholder_text()
        expected_placeholder_text = 'No cameras available on this layout'
        assert layout_3_scene_placeholder_text == expected_placeholder_text, (
            f'Expected: {expected_placeholder_text}'
            f'Actual: {layout_3_scene_placeholder_text}'
            )
        layout_3_scene.activate_show_all_cameras_button()
        all_cameras_layout_scene_2 = Scene(testkit_api, hid)
        all_cameras_layout_cameras_2 = all_cameras_layout_scene_2.get_camera_items()
        assert len(all_cameras_layout_cameras_2) == all_cameras_layout_expected_item_count, (
            f'Expected layout items count: {all_cameras_layout_expected_item_count}.'
            f'Actual items: {all_cameras_layout_cameras_2}'
            )
        actual_all_cameras_layout_item_names_2 = [item.name() for item in all_cameras_layout_cameras_2]
        assert sorted(expected_all_cameras_layout_item_names) == sorted(actual_all_cameras_layout_item_names_2), (
            f'Expected layouts: {expected_all_cameras_layout_item_names}.'
            f'Actual layouts: {actual_all_cameras_layout_item_names_2}'
            )
        actual_title_text = all_cameras_layout_scene_2.get_title_text()
        assert actual_title_text == system_name, (
            f'Expected scene title: {system_name!r}.'
            f'Actual: {actual_title_text!r}'
            )
        left_panel_2 = ApplicationWindow(testkit_api, hid). open_left_panel_widget()
        actual_active_layout_name = left_panel_2.get_active_layout().name()
        assert actual_active_layout_name == root_layout_name, (
            f'Expected active layout name: {root_layout_name}'
            f'Actual: {actual_active_layout_name}'
            )


if __name__ == '__main__':
    exit(test_layouts().main())
