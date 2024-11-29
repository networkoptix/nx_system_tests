# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_upload_several_files_with_multi_selection(VMSTest):
    """Upload several files with multi selection.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41521

    Selection-Tag: xfail
    Selection-Tag: 41521
    Selection-Tag: virtual_cameras
    """

    # TODO: XFAIL reason: https://networkoptix.atlassian.net/browse/VMS-15180
    # Comparison images need to be changed after fixing VMS-15180
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
        with ResourceTree(testkit_api, hid).get_camera('VirtualCamera').open_settings() as camera_settings:
            camera_settings.general_tab.set_auto_min_keep_archive(True)
            camera_settings.general_tab.set_auto_max_keep_archive(True)

        with ResourceTree(testkit_api, hid).get_camera('VirtualCamera').open_settings() as camera_settings:
            upload_dialog = camera_settings.general_tab.open_upload_file_dialog()
            file_paths = [
                gui_prerequisite_supplier.upload_to_remote('upload/avi.avi', client_installation.os_access),
                gui_prerequisite_supplier.upload_to_remote('upload/mkv.mkv', client_installation.os_access),
                gui_prerequisite_supplier.upload_to_remote('upload/mov.mov', client_installation.os_access),
                gui_prerequisite_supplier.upload_to_remote('upload/mp4.mp4', client_installation.os_access),
                ]
            upload_dialog.multi_upload_files(file_paths, 60)

        virtual_camera_scene_item = ResourceTree(testkit_api, hid).get_camera('VirtualCamera').open_in_new_tab()
        virtual_camera_scene_item.wait_for_accessible()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        time.sleep(2)
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2017-11-29T23:36:54'),
            tolerance=(timedelta(seconds=0)),
            )
        scene = Scene(testkit_api, hid)
        loaded_position_one = SavedImage(gui_prerequisite_store.fetch('test41521/vc_screen1.png'))
        scene.wait_until_first_item_is_similar_to(loaded_position_one)
        timeline_navigation.to_end()
        time.sleep(2)
        # VMS-15180
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-06-04T15:52:59'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_position_two = SavedImage(gui_prerequisite_store.fetch('test41521/vc_screen2.png'))
        scene.wait_until_first_item_is_similar_to(loaded_position_two)
        timeline_navigation.to_end()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-06-05T18:57:07'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_position_three = SavedImage(gui_prerequisite_store.fetch('test41521/vc_screen3.png'))
        scene.wait_until_first_item_is_similar_to(loaded_position_three)
        timeline_navigation.to_end()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-08-10T12:06:04'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_position_four = SavedImage(gui_prerequisite_store.fetch('test41521/vc_screen4.png'))
        scene.wait_until_first_item_is_similar_to(loaded_position_four)


if __name__ == '__main__':
    exit(test_upload_several_files_with_multi_selection().main())
