# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_cancel_of_uploading_files(VMSTest):
    """Cancel of uploading folder.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41522

    Selection-Tag: 41522
    Selection-Tag: virtual_cameras
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.add_virtual_camera('VirtualCamera')
        server_vm.api.add_virtual_camera('VirtualCamera2')
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        rtree = ResourceTree(testkit_api, hid)
        with rtree.get_camera('VirtualCamera').open_settings() as camera_settings:
            camera_settings.general_tab.set_auto_min_keep_archive(True)
            camera_settings.general_tab.set_auto_max_keep_archive(True)
        with rtree.get_camera('VirtualCamera2').open_settings() as camera_settings:
            camera_settings.general_tab.set_auto_min_keep_archive(True)
            camera_settings.general_tab.set_auto_max_keep_archive(True)

        # Close by settings
        camera_settings_dialog_1 = rtree.get_camera('VirtualCamera').open_settings()
        upload_dialog_1 = camera_settings_dialog_1.general_tab.open_upload_file_dialog()
        file_path = []
        for local_file in ['upload/avi.avi', 'upload/mkv.mkv', 'upload/mov.mov', 'upload/overlapped_timestamps_1.mkv']:
            file_on_client = gui_prerequisite_supplier.upload_to_remote(local_file, client_installation.os_access)
            file_path.append(file_on_client)
        upload_dialog_1.multi_upload_files(file_path, 0)
        notifications_ribbon = NotificationsRibbon(testkit_api, hid)
        uploading_tile = notifications_ribbon.wait_for_uploading_tile()
        uploading_tile.wait_until_percent(20)
        camera_settings_dialog_1.general_tab.cancel_uploading(close_notification=False)
        MessageBox(testkit_api, hid).wait_until_has_label('Stop uploading?', timeout=10).close_by_button('Stop')
        camera_settings_dialog_1.close()
        rtree.get_camera('VirtualCamera').open_in_new_tab()
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(1)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test41526/screen.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        # Close by widget
        camera_settings_dialog_2 = rtree.get_camera('VirtualCamera2').open_settings()
        upload_dialog_2 = camera_settings_dialog_2.general_tab.open_upload_file_dialog()
        file_path = []
        for local_file in ['upload/avi.avi', 'upload/mkv.mkv', 'upload/mov.mov', 'upload/overlapped_timestamps_1.mkv']:
            file_on_client = gui_prerequisite_supplier.upload_to_remote(local_file, client_installation.os_access)
            file_path.append(file_on_client)
        upload_dialog_2.multi_upload_files(file_path, 0)
        uploading_tile = notifications_ribbon.wait_for_uploading_tile()
        uploading_tile.wait_until_percent(20)
        uploading_tile.cancel_uploading(close_notification=False)
        MessageBox(testkit_api, hid).wait_until_has_label('Stop uploading?', timeout=10).close_by_button('Stop')
        camera_settings_dialog_2.close()
        rtree.get_camera('VirtualCamera2').open_in_new_tab()
        scene.wait_for_items_number(1)
        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test41526/screen.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_cancel_of_uploading_files().main())
