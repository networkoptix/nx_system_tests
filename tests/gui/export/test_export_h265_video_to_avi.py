# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_h265_video_to_avi(VMSTest):
    """Export h265 video to avi.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57359

    Selection-Tag: 57359
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/h265_encoded_video.mp4',
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        export_settings.select_tab('Single Camera')
        export_settings.disable_all_features()

        # TODO: Need to fix in VMS 6.1+
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_57359.avi')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_57359.avi')
        local_file_node.open_in_new_tab().wait_for_accessible()
        scene = Scene(testkit_api, hid)
        assert scene.items()[0].video_is_playing()

        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test57359/result.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_export_h265_video_to_avi().main())
