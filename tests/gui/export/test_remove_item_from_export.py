# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import ProgressDialog
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_remove_item_from_export(VMSTest):
    """Remove item from exported file.

    Export as .nov recordings of two cameras, open the file, delete one item,
    save and reopen the file, check deleted item is absent in the scene.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20931

    Selection-Tag: 20931
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api_1 = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api_1)
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, video_file, 2))
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            camera_count=2,
            )
        rtree = ResourceTree(testkit_api_1, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()

        export_settings = Timeline(testkit_api_1, hid).open_export_video_dialog_for_interval(0, 0.5)
        export_settings.select_tab('Multi Video')
        export_settings.disable_all_multi_video_features()
        export_settings.export_with_specific_path(client_installation.temp_dir() / '20931.nov')

        local_file_node = ResourceTree(testkit_api_1, hid).wait_for_local_file('20931.nov')
        local_file_node.open_in_new_tab()
        camera_1_scene_item.click_button('Close')
        camera_1_scene_item.wait_for_inaccessible()
        ResourceTree(testkit_api_1, hid).get_local_file('20931.nov').save_layout()
        ProgressDialog(testkit_api_1).wait_until_closed(timeout=120)
        # TODO: Need to fix in VMS 6.1+
        ResourceTree(testkit_api_1, hid).get_local_file('20931.nov').open_in_new_tab()
        camera_2_scene_item.wait_for_accessible()
        camera_1_scene_item.wait_for_inaccessible()

        client_installation.kill_client_process()
        testkit_api_2 = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid_2 = HID(testkit_api_2)
        # temporary file opened with menu and may not be available in the list of local files in tree
        MainMenu(testkit_api_2, hid_2).open_file(client_installation.temp_dir() / '20931.nov')
        CameraSceneItem(testkit_api_2, hid, test_camera_2.name).wait_for_accessible()
        CameraSceneItem(testkit_api_2, hid, test_camera_1.name).wait_for_inaccessible()


if __name__ == '__main__':
    exit(test_remove_item_from_export().main())
