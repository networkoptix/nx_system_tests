# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_remove_offline_system_using_shift(VMSTest):
    """Welcome screen remove offline system using shift button.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79190

    Selection-Tag: 79190
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_LOCAL, client_installation] = exit_stack.enter_context(machine_pool.setup_local_bundle_system())
        client_installation.add_fake_welcome_screen_tiles(1)
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        system_name = server_LOCAL.api.get_system_name()
        testkit_api_1 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_1 = HID(testkit_api_1)
        welcome_screen_1 = WelcomeScreen(testkit_api_1, hid_1)
        offline_tile = welcome_screen_1.get_tile_by_system_name('SQUISH_FAKE0')
        welcome_screen_1.wait_for_tile_appear(system_name, 20)
        online_tile = welcome_screen_1.get_tile_by_system_name(system_name)
        assert not offline_tile.is_online()
        assert online_tile.is_online()
        hid_1.keyboard_press('Shift')
        assert offline_tile.has_trash_button()
        assert not online_tile.has_trash_button()
        assert online_tile.has_dropdown_menu()
        hid_1.keyboard_release('Shift')
        offline_tile.remove_using_shift()
        welcome_screen_1.wait_for_tile_disappear(5, 'SQUISH_FAKE0')
        client_installation.kill_client_process()

        testkit_api_2 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_2 = HID(testkit_api_2)
        welcome_screen_2 = WelcomeScreen(testkit_api_2, hid_2)
        welcome_screen_2.wait_for_tile_appear(system_name, 20)
        assert not welcome_screen_2.tile_exists('SQUISH_FAKE0')


if __name__ == '__main__':
    exit(test_remove_offline_system_using_shift().main())
