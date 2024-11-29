# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.gui_test_stand import GuiTestStand
from gui.mobile_ui.app_window import ApplicationWindow
from gui.mobile_ui.connect_to_server import ConnectToServer
from gui.mobile_ui.scene import Scene
from gui.mobile_ui.warning_dialog import WarningDialog
from gui.mobile_ui.welcome_screen import WelcomeScreen
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_6648_connect_to_system(VMSTest):
    """Test connect to system.

    Selection-Tag: 6648
    Selection-Tag: mobile-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6648
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        installer_supplier.distrib().assert_not_older_than('vms_6.1', "Mobile tests only supported by VMS 6.1 and newer")
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        server_vm = exit_stack.enter_context(machine_pool.setup_one_server())
        exit_stack.enter_context(
            playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        [test_camera] = server_vm.api.add_test_cameras(0, 1)
        mobile_client_installation = exit_stack.enter_context(machine_pool.prepared_mobile_client())
        [testkit_api, hid] = mobile_client_installation.start()

        server_ip, server_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username='admin',
            password='WellKnownPassword2',
            )
        WarningDialog(testkit_api, hid).click_button('Connect')
        scene = Scene(testkit_api, hid)
        scene.wait_for_accessible()
        title_label_text = scene.get_title_text()
        system_name = server_vm.api.get_system_name()
        assert title_label_text == system_name, f'Actual server name: {title_label_text}. Expected: {system_name}'
        [camera_item] = scene.get_camera_items()
        actual_camera_name_1 = camera_item.name()
        assert actual_camera_name_1 == test_camera.name, f'Actual camera name: {actual_camera_name_1}. Expected: {test_camera.name}'
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()

        WelcomeScreen(testkit_api, hid).get_server_tile(system_name).activate()
        scene.wait_for_accessible()
        title_label_text = scene.get_title_text()
        assert title_label_text == system_name, f'Actual server name: {title_label_text}. Expected: {system_name}'
        [camera_item] = scene.get_camera_items()
        actual_camera_name_2 = camera_item.name()
        assert actual_camera_name_2 == test_camera.name, f'Actual camera name: {actual_camera_name_2}. Expected: {test_camera.name}'
        ApplicationWindow(testkit_api, hid).open_left_panel_widget().disconnect_from_server()

        server_tile = WelcomeScreen(testkit_api, hid).get_server_tile(system_name)
        server_tile.activate_edit_dialog()
        connect_to_server_dialog = ConnectToServer(testkit_api, hid)
        password_field = connect_to_server_dialog.get_password_field()
        assert not password_field.is_enabled()
        password_field_text = password_field.get_text()
        assert password_field_text == '', 'Password should be hidden'
        connect_to_server_dialog.clear_saved_password()
        password_field.type_text('1234567')
        connect_to_server_dialog.click_connect_button()
        warning_text = connect_to_server_dialog.get_warning_text()
        assert warning_text == 'Invalid login or password'
        connect_to_server_dialog.click_back_button()
        server_tile = WelcomeScreen(testkit_api, hid).get_server_tile(system_name)
        assert not server_tile.get_edit_button().is_accessible(), 'Edit button at server tile should be hidden'


if __name__ == '__main__':
    exit(test_6648_connect_to_system().main())
