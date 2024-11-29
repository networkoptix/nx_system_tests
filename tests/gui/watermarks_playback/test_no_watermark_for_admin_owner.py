# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_no_watermark_for_admin_owner(VMSTest):
    """No watermark for administrator and owner.

    # https://networkoptix.testrail.net/index.php?/cases/view/42980

    Selection-Tag: 42980
    Selection-Tag: watermarks_playback
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        rtree = ResourceTree(testkit_api, hid)
        with rtree.get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.general_tab.reset_image_controls()

        MainMenu(testkit_api, hid).activate_system_administration().enable_watermark()
        rtree.get_camera(test_camera_1.name).open()
        loaded = SavedImage(gui_prerequisite_store.fetch('comparison/camera_no_watermark.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)

        server_vm.api.add_local_admin('Administrator', 'WellKnownPassword2')
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'Administrator', 'WellKnownPassword2')
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_no_watermark_for_admin_owner().main())
