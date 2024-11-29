# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.videowalls import VideowallCreationDialog
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_drag_another_camera_on_screen(VMSTest):
    """Drag another camera on screen.

    # https://networkoptix.testrail.net/index.php?/cases/view/6289

    Selection-Tag: 6289
    Selection-Tag: user_access_rights
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm.api.activate_license(license_server.generate({
            'CLASS2': 'videowall',
            'QUANTITY2': 2,
            'BRAND2': server_vm.api.get_brand(),
            }))
        similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', count=3)
        [test_camera_1, test_camera_2, test_camera_3] = server_vm.api.add_test_cameras(0, 3)
        group_id = server_vm.api.add_user_group('Custom', ['none'])
        user_test1 = server_vm.api.add_local_user(
            'test1',
            'WellKnownPassword2',
            group_id=group_id,
            )
        user_test2 = server_vm.api.add_local_user(
            'test2',
            'WellKnownPassword2',
            group_id=group_id,
            )
        with VideowallCreationDialog(testkit_api, hid) as video_wall:
            video_wall.insert_name('Test wall')
        attach_dialog = ResourceTree(testkit_api, hid).get_videowall('Test wall').open_display_attaching_dialog()
        attach_dialog.attach_single_screen()
        attach_dialog.save_and_close()
        [video_wall] = server_vm.api.list_videowalls()
        server_vm.api.set_user_access_rights(
            user_test1.id,
            [test_camera_1.id, test_camera_2.id, test_camera_3.id],
            )
        server_vm.api.set_user_access_rights(user_test2.id, [test_camera_3.id])
        server_vm.api.set_user_access_rights(
            user_test1.id,
            [video_wall.id],
            access_type='edit',
            )
        server_vm.api.set_user_access_rights(
            user_test2.id,
            [video_wall.id],
            access_type='edit',
            )

        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'test1', 'WellKnownPassword2')
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()
        LayoutTabBar(testkit_api, hid).save_current_as('Test layout')
        rtree = ResourceTree(testkit_api, hid)
        screen = rtree.get_videowall('Test wall').get_single_screen()
        rtree.get_layout('Test layout').drag_n_drop(screen)
        ResourceTree(testkit_api, hid).get_videowall_screen('Screen').open()
        camera_1_scene_item.wait_for_accessible(timeout=6)
        camera_2_scene_item.wait_for_accessible(timeout=6)

        _log_in_using_main_menu(testkit_api, hid, address_port, 'test2', 'WellKnownPassword2')
        ResourceTree(testkit_api, hid).get_videowall_screen('Screen').control_video_wall()
        rtree = ResourceTree(testkit_api, hid)
        screen1 = rtree.get_videowall('Test wall').get_single_screen()
        rtree.get_camera(test_camera_3.name).drag_n_drop(screen1)
        message_dialog = MessageBox(testkit_api, hid).wait_until_appears(20)
        assert message_dialog.get_title() == 'You will lose access to following resources:'
        message = (
            "You are going to delete some resources "
            "to which you have access from Video Wall only. "
            "You will not see them in your resource list "
            "after it and will not be able to add them to Video Wall again.")
        assert message in message_dialog.get_labels()
        message_dialog.close_by_button('Cancel')
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(2)
        camera_1_scene_item.wait_for_accessible()
        camera_2_scene_item.wait_for_accessible()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_camera(test_camera_1.name)
        assert rtree.has_camera(test_camera_2.name)

        screen2 = rtree.get_videowall('Test wall').get_single_screen()
        rtree.get_camera(test_camera_3.name).drag_n_drop(screen2)
        MessageBox(testkit_api, hid).close_by_button('OK')
        scene.wait_for_items_number(1)
        CameraSceneItem(testkit_api, hid, test_camera_3.name).wait_for_accessible()
        rtree = ResourceTree(testkit_api, hid)
        assert not rtree.has_camera(test_camera_1.name)
        assert not rtree.has_camera(test_camera_2.name)


if __name__ == '__main__':
    exit(test_drag_another_camera_on_screen().main())
