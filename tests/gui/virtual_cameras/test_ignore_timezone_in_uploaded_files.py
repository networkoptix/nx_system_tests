# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_ignore_timezone_in_uploaded_files(VMSTest):
    """Ignore timezone in uploaded files.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69792
    # VMS-27244

    Selection-Tag: 69792
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
        with rtree.get_camera('VirtualCamera').open_settings() as camera_settings:
            camera_settings.general_tab.set_ignore_time_zone(False)
            upload_dialog_1 = camera_settings.general_tab.open_upload_file_dialog()
            file_path = gui_prerequisite_supplier.upload_to_remote('upload/DJI_0014.MP4', client_installation.os_access)
            upload_dialog_1.multi_upload_files([file_path], 10)

        virtual_camera_scene_item = rtree.get_camera('VirtualCamera').open_in_new_tab()
        virtual_camera_scene_item.wait_for_accessible()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        time.sleep(2)
        # remove next two repeated steps.step__after fix VMS-27244
        timeline_navigation.to_beginning()
        time.sleep(2)
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2019-09-30T15:10:23'),
            tolerance=(timedelta(seconds=0)),
            )

        server_vm.api.add_virtual_camera('VirtualCamera2')
        ResourceTree(testkit_api, hid).wait_for_camera_on_server(server_vm.api.get_server_name(), 'VirtualCamera2')
        with ResourceTree(testkit_api, hid).get_camera('VirtualCamera2').open_settings() as camera_settings:
            camera_settings.general_tab.set_ignore_time_zone(True)
            upload_dialog_2 = camera_settings.general_tab.open_upload_file_dialog()
            upload_dialog_2.multi_upload_files([file_path], 10)

        virtual_camera_2_scene_item = ResourceTree(testkit_api, hid).get_camera('VirtualCamera2').open_in_new_tab()
        virtual_camera_2_scene_item.wait_for_accessible()
        timeline_navigation.pause_and_to_begin()
        time.sleep(2)
        # remove next two repeated steps.step__after fix VMS-27244
        timeline_navigation.to_beginning()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2019-09-30T12:10:23'),
            tolerance=(timedelta(seconds=0)),
            )


if __name__ == '__main__':
    exit(test_ignore_timezone_in_uploaded_files().main())
