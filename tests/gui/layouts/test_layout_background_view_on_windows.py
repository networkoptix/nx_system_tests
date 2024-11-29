# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_layout_background_view_on_windows(VMSTest):
    """View current background for layout on windows.

    Background is open in viewer app
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/894

    Selection-Tag: 894
    Selection-Tag: layouts
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
        scene = Scene(testkit_api, hid)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.create('Test')
        layout_settings_1 = scene.open_layout_settings()
        remote_background = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings_1.set_background(remote_background)

        ResourceTree(testkit_api, hid).get_layout('Test').open_in_new_tab()
        assert layout_tab_bar.is_open('Test')
        background_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        assert scene.get_background().is_similar_to(background_image, aspect_ratio_error=0.15)
        layout_settings_2 = scene.open_layout_settings()
        layout_settings_2.open_background_tab()
        hid.mouse_left_click_on_object(layout_settings_2.get_view_button())
        _wait_for_microsoft_paint_open(client_installation.os_access)


def _wait_for_microsoft_paint_open(os_access):
    start = time.monotonic()
    while True:
        outcome = os_access.run('tasklist')
        if b'mspaint.exe' in outcome.stdout:
            return
        if time.monotonic() - start > 5:
            raise RuntimeError('mspaint.exe is not open')
        time.sleep(.5)


if __name__ == '__main__':
    exit(test_layout_background_view_on_windows().main())
