# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelinePlaceholder
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_upload_with_overlapping_timestamp(VMSTest):
    """Impossible to upload file with covered timestamp.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41531

    Selection-Tag: 41531
    Selection-Tag: virtual_cameras
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.add_virtual_camera('VirtualCamera')
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        rtree = ResourceTree(testkit_api, hid)
        camera_settings_dialog_1 = rtree.get_camera('VirtualCamera').open_settings()
        upload_dialog_1 = camera_settings_dialog_1.general_tab.open_upload_file_dialog()
        file_path = []
        for local_file in ['upload/overlapped_timestamps_1.mkv', 'upload/overlapped_timestamps_2.mkv']:
            client = gui_prerequisite_supplier.upload_to_remote(local_file, client_installation.os_access)
            file_path.append(client)
        upload_dialog_1.multi_upload_files(file_path, 0)
        message_dialog_1 = MessageBox(testkit_api, hid).wait_until_appears(20)
        assert message_dialog_1.get_title() == 'Some files will not be uploaded'
        assert 'overlapped_timestamps_2.mkv – covers period for which video has already been uploaded.' in message_dialog_1.get_labels()
        message_dialog_1.close_by_button('Cancel')
        rtree.get_camera('VirtualCamera').open_in_new_tab()
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(1)
        assert TimelinePlaceholder(testkit_api).is_enabled()

        camera_settings_dialog_2 = rtree.get_camera('VirtualCamera').open_settings()
        upload_dialog_2 = camera_settings_dialog_2.general_tab.open_upload_file_dialog()
        path = []
        for file in ['upload/overlapped_timestamps_1.mkv', 'upload/overlapped_timestamps_2.mkv']:
            on_client = gui_prerequisite_supplier.upload_to_remote(file, client_installation.os_access)
            path.append(on_client)
        upload_dialog_2.multi_upload_files(path, 0)
        message_dialog_2 = MessageBox(testkit_api, hid).wait_until_appears(20)
        assert message_dialog_2.get_title() == 'Some files will not be uploaded'
        assert 'overlapped_timestamps_2.mkv – covers period for which video has already been uploaded.' in message_dialog_2.get_labels()
        message_dialog_2.close_by_button('OK')
        camera_settings_dialog_2.close()
        rtree.get_camera('VirtualCamera').open_in_new_tab()
        scene.wait_for_items_number(1)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('comparison/vc_screen4.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        camera_settings_dialog_3 = rtree.get_camera('VirtualCamera').open_settings()
        upload_dialog_3 = camera_settings_dialog_3.general_tab.open_upload_file_dialog()
        file_on_client = gui_prerequisite_supplier.upload_to_remote('upload/overlapped_timestamps_2.mkv', client_installation.os_access)
        upload_dialog_3.multi_upload_files([file_on_client], 0)
        message_dialog_3 = MessageBox(testkit_api, hid)
        assert message_dialog_3.wait_until_appears(20).get_title() == 'Selected file covers period for which video has already been uploaded'
        message_dialog_3.close_by_button('OK')

        timeline_navigation.to_beginning()
        assert Timeline(testkit_api, hid).count_archive_chunks() == 1


if __name__ == '__main__':
    exit(test_upload_with_overlapping_timestamp().main())
