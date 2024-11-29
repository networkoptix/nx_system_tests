# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_start_stop_tour_from_context_menu(VMSTest):
    """Start and stop tour from context menu.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1899

    Selection-Tag: 1899
    Selection-Tag: tours
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', count=4))
        test_cameras = server_vm.api.add_test_cameras(0, 4)
        camera_names = [test_camera.name for test_camera in test_cameras]
        ResourceTree(testkit_api, hid).select_cameras(camera_names).open_by_context_menu()
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(len(camera_names))
        scene.start_tour()
        expected_to_be_active = set(camera_names)
        has_been_active = set()
        for _ in range(120):
            time.sleep(.5)
            has_been_active |= {item.name for item in scene.items() if item.in_tour()}
            if has_been_active == expected_to_be_active:
                _logger.debug('All camera were shown in tour')
                break
        else:
            raise RuntimeError(
                f"Expected cameras {expected_to_be_active}, "
                f"shown cameras {has_been_active}")
        scene.stop_tour()


if __name__ == '__main__':
    exit(test_start_stop_tour_from_context_menu().main())
